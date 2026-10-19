import { Color } from 'three';

const PALETTES = {
  diorama: { paper: '#e9e3d5', foliage: '#829982', ground: '#879c7b', water: '#8cb7b2', track: '#be8c78', turf: '#94a78b', asphalt: '#adb0a4', path: '#c8bea8', glass: '#a4b6b3', terracotta: '#bfa38a', roof: '#b2b4a9' },
  white: { paper: '#eeeae3', foliage: '#9da69b', ground: '#b9b6a9', water: '#9daeb3', track: '#b4aaa1', turf: '#b2b7a8', asphalt: '#969e9d', path: '#ded8c9', glass: '#bdc5c3', terracotta: '#d5cfc2', roof: '#e0ddd4' },
  fresh: { paper: '#f1e6cf', foliage: '#438b6c', ground: '#7ca387', water: '#66b8c5', track: '#cc927c', turf: '#7da38a', asphalt: '#8d9f9d', path: '#e4d6b7', glass: '#729eac', terracotta: '#b47e66', roof: '#b7bfb3' },
};

/** Reversible material treatment; streamed geometry and source assets stay intact. */
export class DioramaStyle {
  constructor() { this.enabled = true; this.preset = 'diorama'; this.roots = new Map(); this.materials = new Map(); }

  register(root) {
    if (this.roots.has(root)) return;
    const materials = new Set();
    root.traverse(object => {
      if (!object.isMesh) return;
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
        if (!material?.color || !material.isMeshStandardMaterial) continue;
        materials.add(material);
        if (this.materials.has(material)) continue;
        this.materials.set(material, {
          color: material.color.clone(), roughness: material.roughness, metalness: material.metalness,
          onBeforeCompile: material.onBeforeCompile, customProgramCacheKey: material.customProgramCacheKey,
        });
        this.apply(material);
      }
    });
    this.roots.set(root, materials);
  }

  apply(material) {
    const original = this.materials.get(material);
    material.color.copy(original.color);
    Object.assign(material, { roughness: original.roughness, metalness: original.metalness,
      onBeforeCompile: original.onBeforeCompile, customProgramCacheKey: original.customProgramCacheKey });
    if (this.enabled) {
      const palette = PALETTES[this.preset], paper = new Color(palette.paper);
      const name = material.name.toLowerCase();
      const glazing = /glazing|glass/.test(name);
      const foliage = /trees|planting/.test(name);
      if (/ground_meadow/.test(name)) material.color.set(palette.ground);
      else if (/water|lake/.test(name)) material.color.set(palette.water);
      else if (/track_red/.test(name)) material.color.set(palette.track);
      else if (/turf/.test(name)) material.color.set(palette.turf);
      else if (/asphalt/.test(name)) material.color.set(palette.asphalt);
      else if (/road_v3|curbs/.test(name)) material.color.set(palette.path);
      else if (glazing) material.color.set(palette.glass);
      else if (/terracotta/.test(name)) material.color.set(palette.terracotta);
      else if (/roof|metalwork|alumini|slate/.test(name)) material.color.set(palette.roof);
      else if (/facade|wall|concrete|stone|trim/.test(name)) material.color.copy(original.color).lerp(paper, this.preset === 'white' ? .97 : .78);
      else if (/accent|fins|crest/.test(name)) material.color.copy(original.color).lerp(paper, this.preset === 'white' ? .95 : .45);
      material.roughness = glazing ? .72 : .94;
      material.metalness = 0;
      if (material.vertexColors && (foliage || /campus distance/.test(name))) {
        const tint = new Color(foliage ? palette.foliage : glazing ? palette.glass : palette.paper);
        const strength = this.preset === 'white' ? .94 : foliage ? .55 : glazing ? .76 : .72;
        material.onBeforeCompile = function(shader, renderer) {
          original.onBeforeCompile.call(this, shader, renderer);
          shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>',
            `#include <color_fragment>\ndiffuseColor.rgb = mix(diffuseColor.rgb, vec3(${tint.toArray().join(',')}), ${strength});`);
        };
        const key = `${this.preset}-${foliage}-${glazing}`;
        material.customProgramCacheKey = () => `${original.customProgramCacheKey.call(material)}-paper-v1-${key}`;
      }
    }
    material.needsUpdate = true;
  }

  setEnabled(value) {
    this.enabled = Boolean(value);
    for (const material of this.materials.keys()) this.apply(material);
  }

  setPreset(value) {
    if (value !== 'original' && !Object.hasOwn(PALETTES, value)) throw new Error(`Unknown diorama style: ${value}`);
    if (value !== 'original') this.preset = value;
    this.setEnabled(value !== 'original');
  }

  unregister(root) {
    const removed = this.roots.get(root);
    this.roots.delete(root);
    for (const material of removed || []) {
      if ([...this.roots.values()].some(materials => materials.has(material))) continue;
      const enabled = this.enabled; this.enabled = false; this.apply(material); this.enabled = enabled;
      this.materials.delete(material);
    }
  }
}
