import test from 'node:test';
import assert from 'node:assert/strict';
import { Vector3 } from 'three';
import { plantGeometry } from './CampusLife.js';
import { LAKE_PLANTING } from './LakeEcologyVisuals.js';

test('lake plant geometry keeps finite shaded crowns inside the existing planting budgets', () => {
  const limits = { tall_tree: [.5,1.2,.4], medium_tree: [.42,1.1,.36], shrub: [.6,.85,.43], spreading: [.75,1.1,.60], slender: [.26,1.2,.27] };
  const a = new Vector3(), b = new Vector3(), c = new Vector3();
  let instanceTriangles = 0;
  for (const [type, [halfWidth,height,halfDepth]] of Object.entries(limits)) {
    const geometry = plantGeometry(type);
    try {
      const { position, normal, color } = geometry.attributes;
      assert.ok(position && normal && color);
      assert.equal(normal.count, position.count); assert.equal(color.count, position.count);
      for (const attribute of [position,normal,color]) assert.ok(attribute.array.every(Number.isFinite));
      assert.ok(color.array.every(value => value >= 0 && value <= 1));
      assert.ok(new Set(color.array).size > 25, 'foliage keeps crown and surface colour variation');
      assert.equal(position.count % 3, 0);
      const triangles = position.count / 3;
      assert.ok(triangles > 250 && triangles <= 900, `${type}: ${triangles} triangles`);
      instanceTriangles += triangles * LAKE_PLANTING[type].length;
      for (let i = 0; i < position.count; i += 3) {
        a.fromBufferAttribute(position,i); b.fromBufferAttribute(position,i+1); c.fromBufferAttribute(position,i+2);
        assert.ok(b.sub(a).cross(c.sub(a)).lengthSq() > 1e-14, 'no collapsed branch or crown triangles');
      }
      geometry.computeBoundingBox();
      const { min,max } = geometry.boundingBox;
      assert.ok(min.y >= -.004 && max.y <= height, `${type}: height envelope`);
      assert.ok(Math.max(Math.abs(min.x),Math.abs(max.x)) <= halfWidth, `${type}: crown width envelope`);
      assert.ok(Math.max(Math.abs(min.z),Math.abs(max.z)) <= halfDepth, `${type}: crown depth envelope`);
      const repeat = plantGeometry(type);
      assert.deepEqual(repeat.attributes.position.array, position.array, 'reloading must not randomize planting silhouettes');
      repeat.dispose();
    } finally { geometry.dispose(); }
  }
  assert.equal(Object.values(LAKE_PLANTING).flat().length,23);
  assert.ok(instanceTriangles < 20000, `five batches total ${instanceTriangles} triangles`);
});
