import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { Vector3, Raycaster } from 'three';
import { LakeEcologyVisuals, LAKE_LEVEL, LAKE_PLANTING, inLake, LAKE_RING, distanceToLakeShore, lakeShoreTexture } from './LakeEcologyVisuals.js';
import { sampleLakeBird } from './CampusLife.js';

test('actual lake GLBs: local level patch, submerged terrain, reversible source geometry', async () => {
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const load = async (name, kind) => {
    const bytes = await readFile(new URL(`../../public/campus/${name}`, import.meta.url));
    const { scene } = await loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
    scene.userData.campusLayer = kind;
    return scene;
  };
  const site = await load('site.glb', 'site'), terrain = await load('terrain_1_2.glb', 'terrain');
  const visual = new LakeEcologyVisuals();
  visual.register(site); visual.register(terrain);
  const entries = [...visual.models.values()].flat();
  assert.equal(entries.filter(entry => entry.water).length, 1);
  assert.equal(entries.filter(entry => !entry.water).length, 1);
  let waterCount = 0, originalRange = [Infinity, -Infinity];
  for (const entry of entries) {
    const original = entry.original.attributes.position, updated = entry.geometry.attributes.position;
    assert.equal(original.count, updated.count);
    const affectedNormals = new Set();
    if (!entry.water) for (let i = 0; i < entry.original.index.count; i += 3) {
      const vertices = [0, 1, 2].map(offset => entry.original.index.getX(i + offset));
      if (vertices.some(vertex => original.getY(vertex) !== updated.getY(vertex))) vertices.forEach(vertex => affectedNormals.add(vertex));
    }
    if (!entry.water) assert.ok(affectedNormals.size < 300, 'normal updates stay in the modified lake-bed neighborhood');
    for (let i = 0; i < original.count; i++) {
      assert.equal(updated.getX(i), original.getX(i)); assert.equal(updated.getZ(i), original.getZ(i));
      if (inLake(original.getX(i), original.getZ(i), entry.water ? .025 : 0)) {
        if (entry.water) {
          assert.ok(Math.abs(updated.getY(i) - LAKE_LEVEL) < .00001);
          assert.ok(entry.geometry.attributes.normal.getY(i) > .99999, 'flat water normals must point up, even with compressed source normals');
          waterCount++;
          originalRange = [Math.min(originalRange[0], original.getY(i)), Math.max(originalRange[1], original.getY(i))];
        } else assert.ok(updated.getY(i) <= LAKE_LEVEL - .09999);
      } else assert.equal(updated.getY(i), original.getY(i), 'outside shoreline must stay untouched');
      const normalMayChange = entry.water ? inLake(original.getX(i), original.getZ(i)) : affectedNormals.has(i);
      if (!normalMayChange) for (const axis of ['getX', 'getY', 'getZ']) {
        assert.ok(Math.abs(entry.original.attributes.normal[axis](i) - entry.geometry.attributes.normal[axis](i)) < 1e-7, 'unaffected shading normals must be preserved');
      }
    }
    assert.equal(entry.original.index.count, entry.geometry.index.count, 'preserve triangle count');
  }
  assert.ok(waterCount > 1300);
  assert.ok(originalRange[1] - originalRange[0] > 2, 'regression must cover original warped water');
  assert.ok(!inLake(200, 400), 'peninsula must not be depressed');
  const groundMeshes = entries.filter(entry => !entry.water).map(entry => entry.mesh);
  const ray = new Raycaster(new Vector3(), new Vector3(0, -1, 0));
  // Interior points avoid the intentional water/land boundary interpolation.
  for (const [x,z] of [[240,405],[270,415],[285,495]]) {
    assert.ok(inLake(x,z));
    ray.ray.origin.set(x,100,z);
    const hit = ray.intersectObjects(groundMeshes, false)[0];
    assert.ok(hit && hit.point.y < LAKE_LEVEL);
  }
  const waterEntry = entries.find(entry => entry.water);
  assert.equal(waterEntry.material[0], waterEntry.originalMaterial, 'other water bodies retain their source material');
  const indices = waterEntry.geometry.index, positions = waterEntry.geometry.attributes.position;
  const lakeGroup = waterEntry.geometry.groups[1];
  for (let i = lakeGroup.start; i < lakeGroup.start + lakeGroup.count; i++) {
    const v = indices.getX(i);
    assert.ok(inLake(positions.getX(v), positions.getZ(v)), 'new water shader is restricted to the lake');
  }
  const camera = { position: new Vector3(178, 30, 456) };
  assert.equal(visual.update(12, camera), true); assert.equal(visual.time.value, 12);
  visual.setQuality('low'); visual.update(13, camera); assert.equal(visual.time.value, 0);
  assert.equal(visual.update(14, camera), false, 'Low does not request continuous water rendering');
  visual.setQuality('high'); visual.update(15, camera, false); assert.equal(visual.time.value, 0);
  camera.position.set(3000, 1200, 3000); assert.equal(visual.update(16, camera), false);
  let textureDisposals = 0, materialDisposals = 0, originalDisposals = 0;
  visual.shoreTexture.addEventListener('dispose', () => textureDisposals++);
  waterEntry.material[1].addEventListener('dispose', () => materialDisposals++);
  waterEntry.originalMaterial.addEventListener('dispose', () => originalDisposals++);
  visual.setEnabled(false);
  camera.position.set(178, 30, 456); assert.equal(visual.update(17, camera), false);
  for (const entry of entries) { assert.equal(entry.mesh.geometry, entry.original); assert.equal(entry.mesh.material, entry.originalMaterial); }
  visual.setEnabled(true);
  for (const entry of entries) assert.equal(entry.mesh.geometry, entry.geometry);
  visual.dispose();
  for (const entry of entries) assert.equal(entry.mesh.geometry, entry.original);
  assert.equal(visual.models.size, 0);
  assert.equal(textureDisposals, 1); assert.equal(materialDisposals, 1); assert.equal(originalDisposals, 0);
});

test('shore field follows the mapped bank independently of long water triangles', () => {
  for (const [x,z] of LAKE_RING) assert.ok(distanceToLakeShore(x,z) < 1e-9);
  const texture = lakeShoreTexture(), { data, width, height } = texture.image;
  assert.equal(data.byteLength, 36864, 'shore detail uses a small single-channel texture');
  const sample = (x,z) => {
    const u = (x - 148.3) / 158.8 * width - .5, v = (z - 376.3) / 162.9 * height - .5;
    const i = Math.floor(u), j = Math.floor(v), tx = u - i, tz = v - j;
    const at = (a,b) => data[Math.max(0,Math.min(height-1,b))*width+Math.max(0,Math.min(width-1,a))] / 255 * 12;
    return (at(i,j)*(1-tx)+at(i+1,j)*tx)*(1-tz)+(at(i,j+1)*(1-tx)+at(i+1,j+1)*tx)*tz;
  };
  for (let z = 378; z < 538; z += 3.1) for (let x = 150; x < 306; x += 3.3) if (inLake(x,z)) {
    const exact = Math.min(12,distanceToLakeShore(x,z));
    assert.ok(Math.abs(sample(x,z)-exact) < .65, 'sub-metre sampling error at lake interior points');
    if (exact > 3) assert.ok(sample(x,z) > 2.25, 'deep interior cannot acquire an artificial shoreline band');
  }
  texture.dispose();
});

test('lake planting stays illustrative and bird orbit remains near the sample', () => {
  assert.equal(Object.keys(LAKE_PLANTING).length, 5);
  assert.equal(Object.values(LAKE_PLANTING).flat().length, 23);
  for (const [x,y,z] of Object.values(LAKE_PLANTING).flat()) {
    assert.ok(Number.isFinite(y)); assert.ok(!inLake(x,z));
  }
  const position = new Vector3();
  for (let time = 0; time <= 120; time += 3) for (let bird = 0; bird < 6; bird++) {
    sampleLakeBird(time, bird, position);
    assert.ok(position.x >= 177 && position.x <= 297 && position.z >= 394 && position.z <= 450);
    assert.ok(position.y >= 22 && position.y <= 35.25);
  }
});
