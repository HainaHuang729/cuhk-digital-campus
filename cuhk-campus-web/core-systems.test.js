import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { CameraFlight } from './src/core/CameraFlight.js';
import { BuildingInteraction } from './src/systems/BuildingInteraction.js';
import { QualitySystem } from './src/systems/QualitySystem.js';
import { StreamingSystem } from './src/systems/StreamingSystem.js';
import { TimeOfDaySystem } from './src/systems/TimeOfDaySystem.js';

function cameraRig() {
  const camera = new THREE.PerspectiveCamera();
  camera.position.set(0, 100, 100);
  const controls = new THREE.EventDispatcher();
  controls.target = new THREE.Vector3();
  return { camera, controls };
}

test('camera flight preserves both endpoints, lifts the middle and cancels on orbit input', () => {
  const { camera, controls } = cameraRig();
  let completed = 0;
  const flight = new CameraFlight(camera, controls, { onComplete: () => completed++ });
  flight.flyTo([100, 100, 100], [100, 0, 0], 1000);
  const start = flight.active.start = 0;
  flight.update(start);
  assert.deepEqual(camera.position.toArray(), [0, 100, 100]);
  flight.update(start + 500);
  assert.ok(controls.target.distanceTo(new THREE.Vector3(50, 0, 0)) < 1e-10);
  assert.ok(Math.abs(camera.position.x - 50) < 1e-10);
  assert.ok(camera.position.y > 110, 'the middle should clear intervening terrain');
  flight.update(start + 1000);
  assert.ok(camera.position.distanceTo(new THREE.Vector3(100, 100, 100)) < 1e-10);
  assert.deepEqual(controls.target.toArray(), [100, 0, 0]);
  assert.equal(completed, 1);
  assert.equal(flight.active, null);
  flight.flyTo([0, 200, 0], [0, 0, 0]);
  controls.dispatchEvent({ type: 'start' });
  assert.equal(flight.active, null);
});

test('camera constraints clear the highest local terrain cell and building roof throughout a flight', () => {
  const { camera, controls } = cameraRig();
  const flight = new CameraFlight(camera, controls);
  flight.ground = { xmin: -100, zmin: -100, step: 100, cols: 3, rows: 3, heights: [10, 20, 30, 40, 50, 60, 70, 80, 90] };
  camera.position.set(-50, 1, -50);
  assert.equal(flight.constrain(), true);
  assert.equal(camera.position.y, 62);
  flight.buildings = [{ id: '123', position: [0, 90, 0], size: [40, 60, 40] }];
  flight.flyTo([10, 30, 10], [0, 50, 0], 1000);
  const start = flight.active.start = 0;
  for (let ms = 0; ms <= 1000; ms += 25) {
    flight.update(start + ms);
    flight.constrain();
    if (Math.abs(camera.position.x) < 25 && Math.abs(camera.position.z) < 25) assert.ok(camera.position.y >= 132);
  }
});

test('clamping camera coordinates reports a changed frame even when height is already safe', () => {
  const { camera, controls } = cameraRig();
  const flight = new CameraFlight(camera, controls);
  camera.position.set(5000, 900, -5000);
  assert.equal(flight.constrain(), true, 'the render-on-demand loop must draw the clamped camera');
  assert.deepEqual(camera.position.toArray(), [4500, 900, -4500]);
});

test('automatic quality requires sustained slow frames, respects cooldown, and never overrides manual quality', () => {
  const oldDpr = globalThis.devicePixelRatio;
  globalThis.devicePixelRatio = 2;
  try {
    const ratios = [], levels = [];
    const quality = new QualitySystem({ setPixelRatio: n => ratios.push(n) }, { onChange: n => levels.push(n) });
    const first = quality.lastChange;
    quality.update(20, first + 10000);
    assert.equal(quality.slowSince, null);
    quality.update(20, first + 21000);
    quality.update(20, first + 28500);
    assert.equal(quality.level, 'high');
    quality.update(50, first + 28900);
    assert.equal(quality.slowSince, null, 'a recovered frame resets the sustained-low interval');
    quality.update(20, first + 29000);
    quality.update(20, first + 37100);
    assert.equal(quality.level, 'medium');
    const second = quality.lastChange;
    quality.update(10, second + 19999);
    assert.equal(quality.level, 'medium');
    quality.update(10, second + 21000, true);
    assert.equal(quality.slowSince, null, 'loading and camera flights do not count as a slow-device sample');
    quality.set('high', false);
    quality.update(1, quality.lastChange + 60000);
    quality.update(1, quality.lastChange + 100000);
    assert.equal(quality.level, 'high');
    assert.deepEqual(levels, ['medium', 'high']);
    assert.ok(ratios.every(value => value <= 1.5));
  } finally {
    if (oldDpr === undefined) delete globalThis.devicePixelRatio;
    else globalThis.devicePixelRatio = oldDpr;
  }
});

function lightingRig() {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera();
  const sun = new THREE.DirectionalLight(), fill = new THREE.HemisphereLight();
  scene.add(sun, sun.target, fill);
  const time = new TimeOfDaySystem({ scene, renderer: { shadowMap: {} }, sun, fill });
  const interaction = new BuildingInteraction({ camera, buildings: [{ id: '123', position: [0, 10, 0], size: [10, 20, 10] }], timeSystem: time, requestRender() {} });
  const makeBuilding = () => {
    const root = new THREE.Group();
    const material = new THREE.MeshStandardMaterial({ name: 'M_Photo_ShadowGlazing', color: '#385061' });
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 20, 10), material);
    mesh.userData.osm_id = '123'; root.add(mesh);
    return { root, mesh, material };
  };
  return { scene, camera, time, interaction, makeBuilding };
}

test('selecting at night does not bake night emission into a highlight after returning to noon', () => {
  const { time, interaction, makeBuilding } = lightingRig();
  const { root, mesh, material } = makeBuilding();
  time.registerModel(root); interaction.register(root);
  time.setTime(22); interaction.setSelected('123');
  assert.notEqual(mesh.material, material);
  assert.ok(mesh.material.emissive.r > .5);
  time.setTime(12);
  assert.equal(material.emissive.getHex(), 0);
  assert.equal(mesh.material.emissive.getHex(), 0, 'selection must follow the same day/night material baseline');
  interaction.setSelected(null);
  assert.equal(mesh.material, material);
  time.dispose(); mesh.geometry.dispose(); material.dispose();
});

test('unloading a selected detail zone restores the low building and disposes only its own resources', async () => {
  const { scene, time, interaction, makeBuilding } = lightingRig();
  const low = makeBuilding(), high = makeBuilding();
  let lowDisposed = 0, highDisposed = 0, cloneDisposed = 0;
  low.material.addEventListener('dispose', () => lowDisposed++);
  high.material.addEventListener('dispose', () => highDisposed++);
  const add = root => { time.registerModel(root); interaction.register(root); };
  const remove = root => { interaction.unregister(root); time.unregisterModel(root); };
  scene.add(low.root); add(low.root);
  const loader = { setMeshoptDecoder() {}, async loadAsync() { return { scene: high.root }; } };
  const streaming = new StreamingSystem({ scene, loader, buildings: [], onAdd: add, onRemove: remove });
  streaming.lowBuildings.set('123', low.root);
  streaming.desired.set('zone', 'high');
  await streaming.loadZone({ id: 'zone', buildings: ['123'], levels: { high: { url: '/fake.glb', bytes: 128 } } }, 'high');
  assert.equal(low.root.visible, false);
  time.setTime(22); interaction.setSelected('123');
  const selectedHigh = high.mesh.material;
  selectedHigh.addEventListener('dispose', () => cloneDisposed++);
  streaming.removeZone('zone');
  assert.equal(low.root.visible, true);
  assert.equal(high.root.parent, null);
  assert.equal(highDisposed, 1);
  assert.equal(cloneDisposed, 1);
  assert.equal(lowDisposed, 0);
  assert.equal(interaction.meshes.get('123').size, 1);
  assert.ok(!time.materials.has(high.material));
  assert.ok(low.mesh.material.emissive.r > .5);
  interaction.setSelected(null);
  assert.equal(low.mesh.material, low.material);
  remove(low.root); time.dispose(); low.mesh.geometry.dispose(); low.material.dispose();
});
