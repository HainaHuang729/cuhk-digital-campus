import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { sampleTimeOfDay, TimeOfDaySystem } from './TimeOfDaySystem.js';

test('time wraps continuously and all 24 hours keep finite light values', () => {
  assert.equal(sampleTimeOfDay(24).hours, 0);
  assert.equal(sampleTimeOfDay(-1).hours, 23);
  assert.equal(sampleTimeOfDay(NaN).hours, 12);
  for (let t = 0; t <= 24; t += .01) {
    const state = sampleTimeOfDay(t);
    assert.ok(state.nightAmount >= 0 && state.nightAmount <= 1);
    assert.ok(state.exposure > 0 && state.sunIntensity >= 0);
    assert.ok(state.sunDirection.toArray().every(Number.isFinite));
    const next = sampleTimeOfDay(t + .001);
    assert.ok(Math.abs(next.nightAmount - state.nightAmount) < .003);
    assert.ok(Math.abs(next.exposure - state.exposure) < .003);
  }
  assert.equal(sampleTimeOfDay(22).nightAmount, 1);
  assert.equal(sampleTimeOfDay(12).nightAmount, 0);
  assert.ok(sampleTimeOfDay(12).sunElevation > 65);
  assert.ok(Math.abs(sampleTimeOfDay(23.999).nightAmount - sampleTimeOfDay(.001).nightAmount) < .001);
});

test('night materials register, survive partial streaming unload, and restore without point lights', () => {
  const scene = new THREE.Scene();
  const renderer = { shadowMap: {}, toneMappingExposure: 1 };
  const sun = new THREE.DirectionalLight();
  const fill = new THREE.HemisphereLight();
  scene.add(sun, sun.target, fill);
  const time = new TimeOfDaySystem({ scene, renderer, sun, fill });
  const material = new THREE.MeshStandardMaterial({ name: 'M_Detail_glazing', envMapIntensity: .3 });
  const a = new THREE.Mesh(new THREE.BoxGeometry(), material);
  const b = new THREE.Mesh(a.geometry, material);
  time.registerModel(a);
  const cleanup = time.registerModel(b);
  time.setTime(22);
  assert.ok(material.emissive.r > .5);
  assert.equal(material.envMapIntensity, 1);
  time.unregisterModel(a);
  assert.equal(time.materials.get(material).count, 1);
  cleanup();
  assert.equal(material.emissive.getHex(), 0);
  assert.equal(material.envMapIntensity, .3);
  assert.ok(!scene.children.some(object => object.isPointLight));
  time.setPlaying(true);
  time.update(.1);
  assert.ok(time.state.hours > 22);
  time.dispose();
  material.dispose();
  a.geometry.dispose();
});
