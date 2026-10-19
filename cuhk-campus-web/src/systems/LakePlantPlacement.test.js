import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { DoubleSide, Raycaster, Vector3 } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { LAKE_PLANTING } from './LakeEcologyVisuals.js';

const cross = (a,b,c) => (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);
function convexHull(points) {
  const sorted = [...new Map(points.map(p => [p.join(','),p])).values()].sort((a,b) => a[0]-b[0] || a[1]-b[1]);
  const half = rows => {
    const chain = [];
    for (const point of rows) {
      while (chain.length > 1 && cross(chain.at(-2),chain.at(-1),point) <= 0) chain.pop();
      chain.push(point);
    }
    return chain.slice(0,-1);
  };
  return [...half(sorted),...half(sorted.toReversed())];
}

test('actual lake planting avoids site surfaces, buildings and the running-track interior', async () => {
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const load = async name => {
    const bytes = await readFile(new URL(`../../public/campus/${name}`,import.meta.url));
    const { scene } = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),'');
    scene.updateMatrixWorld(true);
    scene.traverse(object => {
      if (object.isMesh) for (const material of Array.isArray(object.material) ? object.material : [object.material]) material.side = DoubleSide;
    });
    return scene;
  };
  const [site,terrain,buildings] = await Promise.all(['site.glb','terrain_1_2.glb','buildings-low.glb'].map(load));
  const ray = new Raycaster(new Vector3(),new Vector3(0,-1,0));
  const hits = (root,x,z) => { ray.ray.origin.set(x,1000,z); return ray.intersectObject(root,true); };
  // The convex running oval encloses grass too: surface raycasts alone miss that exclusion.
  const track = hits(site,223,438).find(hit => /Track_red_rubber/.test(hit.object.material.name));
  assert.ok(track,'known point must identify the actual Chung Chi running-track mesh');
  const points = [], position = track.object.geometry.attributes.position, world = new Vector3();
  for (let i = 0; i < position.count; i++) {
    world.fromBufferAttribute(position,i).applyMatrix4(track.object.matrixWorld);
    // Other sports surfaces share this material; the levelled oval has its own elevation.
    if (Math.abs(world.y-track.point.y) < .01) points.push([world.x,world.z]);
  }
  const hull = convexHull(points);
  assert.ok(hull.length >= 8 && points.length > 100);
  assert.ok(hull.every(([x,z]) => x > 160 && x < 275 && z > 420 && z < 630),'isolate this oval, not the other sports grounds');
  const inTrack = (x,z) => hull.every((a,i) => cross(a,hull[(i+1)%hull.length],[x,z]) >= -1e-5);
  const blocked = (x,z) => inTrack(x,z) || hits(site,x,z).length > 0 || hits(buildings,x,z).length > 0;
  for (const [type,anchors] of Object.entries(LAKE_PLANTING)) for (const [index,[x,y,z]] of anchors.entries()) {
    assert.ok(!blocked(x,z),`${type}[${index}] at ${x},${z} intersects a site surface, building or sports enclosure`);
    const ground = hits(terrain,x,z)[0];
    assert.ok(ground && Math.abs(ground.point.y-y) < .01,`${type}[${index}] root must sit on the real terrain`);
  }
  for (const [x,z] of [[223,438],[184,451],[262,490],[197,438],[249,464],[262,516]]) {
    assert.ok(blocked(x,z),`regression must reject former sports-ground anchor ${x},${z}`);
  }
  const geometries = new Set(), materials = new Set();
  for (const root of [site,terrain,buildings]) root.traverse(object => {
    if (object.geometry) geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) if (material) materials.add(material);
  });
  geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose());
});
