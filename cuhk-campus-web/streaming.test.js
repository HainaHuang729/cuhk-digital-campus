import test from 'node:test';
import assert from 'node:assert/strict';
import { Scene, Group, Mesh, BoxGeometry, MeshStandardMaterial, PerspectiveCamera, Vector3 } from 'three';
import { StreamingSystem } from './src/systems/StreamingSystem.js';

function fixture() {
  const buildings = Array.from({ length: 369 }, (_, i) => ({ id: String(i + 1), position: [0, 0, 0], size: [20, 20, 20] }));
  let disposed = 0;
  const root = (low = false) => {
    const group = new Group();
    for (const building of low ? buildings : buildings.slice(0, 1)) {
      const node = new Group(); node.userData.osm_id = building.id;
      const geometry = new BoxGeometry(); geometry.addEventListener('dispose', () => disposed++);
      node.add(new Mesh(geometry, new MeshStandardMaterial())); group.add(node);
    }
    return group;
  };
  const zone = { id: 'zone', buildings: ['1'], levels: { medium: { url: '/medium', bytes: 200 }, high: { url: '/high', bytes: 400 } } };
  const manifest = { initial: [{ url: '/low', kind: 'buildings-low', bytes: 100 }], zones: [zone] };
  const loader = { setMeshoptDecoder() {}, loadAsync: async url => ({ scene: root(url === '/low') }) };
  const removed = [];
  const stream = new StreamingSystem({ scene: new Scene(), buildings, loader, onRemove: item => removed.push(item) });
  return { stream, loader, zone, manifest, root, removed, disposed: () => disposed };
}

test('stream replacement, downgrade and disposal retain all low buildings and account current assets', async () => {
  const f = fixture(); const previousFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: true, json: async () => f.manifest });
  try {
    assert.equal(await f.stream.loadInitial(), f.manifest);
    assert.equal(f.stream.lowBuildings.size, 369);
    assert.equal(f.stream.loadedBytes, 100);
    f.stream.desired.set('zone', 'medium'); await f.stream.loadZone(f.zone, 'medium');
    assert.equal(f.stream.loadedBytes, 300);
    assert.equal(f.stream.lowBuildings.get('1').visible, false);
    f.stream.desired.set('zone', 'high'); await f.stream.loadZone(f.zone, 'high');
    assert.equal(f.stream.loadedBytes, 500);
    assert.equal(f.removed.length, 1);
    assert.equal(f.disposed(), 1);
    f.stream.removeZone('zone');
    assert.equal(f.stream.loadedBytes, 100);
    assert.equal(f.stream.lowBuildings.get('1').visible, true);
    f.stream.dispose(); assert.equal(f.stream.loadedBytes, 0); assert.equal(f.disposed(), 371);
  } finally { globalThis.fetch = previousFetch; }
});

test('late zone response is released when the camera no longer needs it', async () => {
  const f = fixture(); let finish;
  f.loader.loadAsync = () => new Promise(resolve => { finish = resolve; });
  f.stream.desired.set('zone', 'high');
  const pending = f.stream.loadZone(f.zone, 'high');
  f.stream.desired.clear(); finish({ scene: f.root() }); await pending;
  assert.equal(f.stream.active.size, 0); assert.equal(f.stream.loadedBytes, 0);
  assert.equal(f.stream.pending.size, 0); assert.equal(f.stream.loadingCount, 0); assert.equal(f.disposed(), 1);
});

test('quality, distance control and hysteresis avoid repeated high-detail downloads at the boundary', () => {
  const f = fixture(); f.stream.manifest = f.manifest;
  const requests = []; f.stream.loadZone = (_, level) => { requests.push(level); };
  const camera = new PerspectiveCamera(), target = new Vector3();
  f.stream.active.set('zone', { level: 'high', lastWanted: performance.now() });
  camera.position.set(172, 0, 0); f.stream.update(camera, target, null);
  assert.deepEqual(requests, []); // 165m after building size adjustment, inside 180m exit.
  camera.position.set(195, 0, 0); f.stream.lastUpdate = -Infinity; f.stream.update(camera, target, null);
  assert.deepEqual(requests, ['medium']);
  f.stream.setDistanceScale(2); assert.equal(f.stream.distanceScale, 1.5);
  f.stream.setDistanceScale(.2); assert.equal(f.stream.distanceScale, .5);
  f.stream.setQuality('low'); f.stream.update(camera, target, '1');
  assert.equal(f.stream.desired.get('zone'), 'medium');
});

test('failed detail preserves an existing loaded zone and cleans pending accounting', async () => {
  const f = fixture(); const warn = console.warn;
  console.warn = () => {};
  try {
    f.stream.desired.set('zone', 'medium'); await f.stream.loadZone(f.zone, 'medium');
    f.loader.loadAsync = async () => { throw new Error('offline'); };
    f.stream.desired.set('zone', 'high'); await f.stream.loadZone(f.zone, 'high');
    assert.equal(f.stream.active.get('zone').level, 'medium');
    assert.equal(f.stream.loadedBytes, 200); assert.equal(f.stream.loadingCount, 0);
    assert.equal(f.stream.pending.size, 0); assert.equal(f.stream.errors.size, 1);
    f.stream.dispose();
  } finally { console.warn = warn; }
});
