import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as THREE from 'three';
import { CampusLife, samplePath } from './src/systems/CampusLife.js';

test('real campus routes stay finite; instancing quality and toggles preserve original placement', async () => {
  const data = JSON.parse(readFileSync(new URL('./public/campus/life.json', import.meta.url)));
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => data });
  // Renderer-free check of instance transforms. GLB decoding is checked separately in Blender.
  const templates = new THREE.Group();
  for (const entry of data.treeTemplates) for (const name of Object.values(entry)) {
    const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 0), new THREE.MeshStandardMaterial());
    mesh.name = name;
    templates.add(mesh);
  }
  const system = new CampusLife({ scene: new THREE.Scene(), loader: { loadAsync: async () => ({ scene: templates }) } });
  try {
    await system.load();
    assert.equal(system.trees.length, 1374);
    assert.equal(system.treeMeshes.flat().length, 16);
    assert.equal(system.getStats().furniture, 15);
    assert.equal(system.getStats().nightPools, 0);
    system.setNightAmount(1);
    assert.equal(system.getStats().nightPools, 40);
    assert.equal(system.lampPools.material.depthTest, true);
    assert.equal(system.lampPools.material.depthWrite, false);
    system.setNightAmount(0);
    assert.equal(system.getStats().nightPools, 0);
    for (const tree of system.trees) assert.ok(tree.position.distanceTo(new THREE.Vector3().setFromMatrixPosition(tree.matrix)) < .0001);
    const p = new THREE.Vector3(), direction = new THREE.Vector3();
    for (const path of system.paths) for (const at of [0, .5, .999, 1, 1.3, 1.999, 2, 7.8]) {
      samplePath(path, path.length * at, p, direction);
      assert.ok([...p, ...direction].every(Number.isFinite));
      assert.ok(Math.abs(direction.length() - 1) < .000001);
    }
    const camera = new THREE.PerspectiveCamera(50, 1.6, .1, 8000);
    camera.position.set(-120, 180, 200);
    camera.lookAt(-100, 100, 0);
    camera.updateMatrixWorld();
    system.update(1, 1 / 60, camera);
    assert.ok(system.getStats().people > 0);
    assert.ok(system.getStats().people <= 24);
    assert.ok(system.getStats().trees > 0);
    for (const mesh of system.group.children) assert.ok(Array.from(mesh.instanceMatrix.array).every(Number.isFinite), mesh.name);
    system.setQuality('low');
    system.update(2, 1 / 60, camera);
    assert.ok(system.getStats().people <= 10);
    system.setPeopleEnabled(false);
    system.setVegetationEnabled(false);
    system.update(3, 1 / 60, camera);
    assert.deepEqual([system.getStats().people, system.getStats().trees, system.getStats().cars, system.getStats().bicycles], [0, 0, 0, 0]);
    system.setVegetationEnabled(true);
    assert.equal(system.update(4, 1 / 60, camera, false), true, 'changed culling must request a reduced-motion frame');
    assert.equal(system.update(5, 1 / 60, camera, false), false, 'a stationary reduced-motion scene stays idle');
    camera.lookAt(100, 100, 0);
    assert.equal(system.update(6, 1 / 60, camera, false), true, 'rotation must refresh a reduced-motion scene');
    assert.equal(system.wind.value, 0, 'culling time must not animate trees in reduced-motion mode');
    system.dispose();
    assert.equal(system.group.children.length, 0);
  } finally { globalThis.fetch = originalFetch; }
});

test('tree culling follows rotation without moving the camera or advancing animation time', () => {
  const system = new CampusLife({ scene: new THREE.Scene() });
  const geometry = new THREE.BoxGeometry(), material = new THREE.MeshStandardMaterial();
  system.trees = [-50, 50].map(z => ({ template: 0, position: new THREE.Vector3(0, 0, z), matrix: new THREE.Matrix4().makeTranslation(0, 0, z) }));
  system.treeMeshes = [[system.mesh(geometry, material, 2, 'near'), system.mesh(geometry, material, 2, 'far')]];
  const camera = new THREE.PerspectiveCamera(45, 1, 1, 1000);
  camera.position.set(0, 2, 0);
  camera.lookAt(0, 2, -50);
  const matrix = new THREE.Matrix4();
  try {
    assert.equal(system.cullTrees(camera, 0), true);
    assert.equal(system.treeMeshes[0][0].count, 1);
    system.treeMeshes[0][0].getMatrixAt(0, matrix);
    assert.equal(matrix.elements[14], -50);
    camera.lookAt(0, 2, 50);
    assert.equal(system.cullTrees(camera, 0), true);
    assert.equal(system.treeMeshes[0][0].count, 1);
    system.treeMeshes[0][0].getMatrixAt(0, matrix);
    assert.equal(matrix.elements[14], 50, 'the newly visible tree must replace the tree behind the camera');
    assert.equal(system.cullTrees(camera, 1), false);
    camera.aspect = 2;
    camera.updateProjectionMatrix();
    assert.equal(system.cullTrees(camera, 1), true, 'viewport changes invalidate culling too');
  } finally { system.dispose(); }
});
