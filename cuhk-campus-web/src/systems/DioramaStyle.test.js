import test from 'node:test';
import assert from 'node:assert/strict';
import { Group, Mesh, BoxGeometry, MeshStandardMaterial } from 'three';
import { DioramaStyle } from './DioramaStyle.js';

test('paper treatment restores shared streamed materials and preserves shader hooks', () => {
  const material = new MeshStandardMaterial({ name: 'Campus trees / original vertex colours', vertexColors: true, color: '#225522', roughness: .6, metalness: .2 });
  const hook = shader => { shader.uniforms.wind = { value: 1 }; };
  material.onBeforeCompile = hook;
  const original = material.color.clone(), geometry = new BoxGeometry();
  const a = new Group(), b = new Group();
  a.add(new Mesh(geometry, material)); b.add(new Mesh(geometry, material));
  const style = new DioramaStyle(); style.register(a); style.register(b); style.register(a);
  const shader = { uniforms: {}, fragmentShader: '#include <color_fragment>' };
  material.onBeforeCompile(shader);
  assert.equal(shader.uniforms.wind.value, 1);
  assert.match(shader.fragmentShader, /mix\(diffuseColor/);
  assert.equal(material.roughness, .94);
  style.unregister(a); assert.equal(style.materials.size, 1);
  style.setEnabled(false);
  assert.deepEqual(material.color, original); assert.equal(material.onBeforeCompile, hook);
  assert.equal(material.roughness, .6); assert.equal(material.metalness, .2);
  style.setEnabled(true); style.unregister(b);
  assert.equal(style.materials.size, 0); assert.deepEqual(material.color, original);
  assert.equal(a.children[0].geometry, geometry);
  geometry.dispose(); material.dispose();
});

test('newly streamed facades follow the active style without changing glazing identity', () => {
  const style = new DioramaStyle(); style.setEnabled(false);
  const material = new MeshStandardMaterial({ name: 'M_Photo_ShadowGlazing', color: '#163436' });
  const mesh = new Mesh(new BoxGeometry(), material), original = material.color.clone();
  style.register(mesh); assert.deepEqual(material.color, original);
  style.setEnabled(true); assert.equal(material.color.getHexString(), 'a4b6b3');
  assert.match(material.name, /Glazing/);
  style.setEnabled(false); assert.deepEqual(material.color, original);
  style.unregister(mesh); mesh.geometry.dispose(); material.dispose();
});

test('sample presets use distinct shader programs and restore source colours after cycling', () => {
  const style = new DioramaStyle();
  const material = new MeshStandardMaterial({ name: 'Campus distance colors', vertexColors: true });
  const mesh = new Mesh(new BoxGeometry(), material), keys = new Set(), shaders = new Set();
  style.register(mesh);
  for (const preset of ['diorama', 'white', 'fresh', 'diorama']) {
    style.setPreset(preset);
    keys.add(material.customProgramCacheKey());
    const shader = { uniforms: {}, fragmentShader: '#include <color_fragment>' };
    material.onBeforeCompile(shader); shaders.add(shader.fragmentShader);
  }
  assert.equal(keys.size, 3); assert.equal(shaders.size, 3);
  assert.throws(() => style.setPreset('unknown'));
  style.setPreset('original'); assert.equal(material.color.getHexString(), 'ffffff');
  style.unregister(mesh); mesh.geometry.dispose(); material.dispose();
});
