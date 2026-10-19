import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as THREE from '../../../cuhk-campus-web/node_modules/three/build/three.module.js';
import {CalibrationLayer} from '../../../cuhk-campus-web/src/systems/CalibrationLayer.js';

const bytes = await readFile(new URL('../../../cuhk-campus-web/public/calibration/shaw-reference.json', import.meta.url));
const data = JSON.parse(bytes);
assert(bytes.length < 1_500_000);
assert.equal(data.defaultVisible, false);
assert.equal(data.metrics.correctionApplied, false);
assert.deepEqual(data.coordinateSystem.originHK1980, [839400,831150,0]);
assert.equal(data.coordinateSystem.localScale, 1);
assert(data.metrics.footprint.intersectionOverUnion > .8);
assert(Math.abs(data.coordinateSystem.sourceHeightConversion.centerResidualM) < .01);
assert(data.coordinateSystem.sourceHeightConversion.maximumControlXYDifferenceM < .05);
const scene = new THREE.Scene(); let renders = 0; let fetches = 0;
globalThis.fetch = async () => { fetches++; return {ok:true, json:async () => structuredClone(data)}; };
const layer = new CalibrationLayer(scene, () => renders++);
assert.equal(fetches,0); assert.equal(layer.group.visible,false);
await Promise.all([layer.load(),layer.load()]); assert.equal(fetches,1);
const attr=layer.building.geometry.attributes.position;
const initial=Array.from(attr.array); const modelBounds=layer.modelBox.box.clone();
layer.setVerticalMode('source');
for(let i=0;i<attr.count;i++) {
  assert.equal(attr.getX(i),initial[i*3]); assert.equal(attr.getZ(i),initial[i*3+2]);
  assert(Math.abs(attr.getY(i)-(data.building.positions[i*3+1]-data.building.heightShift[i])) < .00002);
}
assert(layer.modelBox.box.equals(modelBounds));
assert(Math.abs(layer.referenceBox.box.max.y-111.6)<.005);
layer.setVerticalMode('hkpd'); assert.deepEqual(Array.from(attr.array),initial);
layer.setOpacity(.25); assert.equal(layer.building.material.opacity,.25);
layer.setBoundsVisible(false); assert.equal(layer.referenceBox.visible,false);
layer.setVisible(true); assert.equal(layer.group.visible,true);
layer.setVisible(false); assert.equal(layer.group.visible,false);
layer.dispose(); assert.equal(scene.children.length,0); assert(renders>0);
console.log('Calibration checks passed: lazy bounded load, CRS controls, reversible vertical diagnostics, opacity, bounds, disposal.');
