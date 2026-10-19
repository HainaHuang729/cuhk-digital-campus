import * as THREE from 'three';

// OSM 33411938 from the existing geodata.json, EPSG:2326 -> (E-839400, H, 831150-N).
// This is a mapped shoreline, not a surveyed water-level or botanical inventory.
export const LAKE_LEVEL = 6.555535; // Median of existing lake water vertices; display elevation only.
export const LAKE_RING = [[172.028,410.329],[171.348,412.322],[160.928,405.392],[165.663,400.918],[170.223,396.266],[174.587,391.437],[178.056,386.807],[182.307,382.875],[187.197,379.774],[192.571,377.602],[198.254,376.438],[203.906,376.337],[247.705,377.501],[253.708,378.12],[262.552,380.344],[274.074,385.225],[287.296,394.679],[298.129,402.716],[305.554,409.968],[307.029,421.417],[302.275,433.023],[292.806,447.643],[291.336,456.358],[294.447,466.6],[292.864,476.866],[289.437,483.057],[287.328,489.89],[287.659,499.036],[289.967,508.194],[291.989,523.098],[291.941,539.166],[277.619,539.003],[277.266,524.253],[276.664,503.634],[274.794,473.98],[273.092,461.068],[265.173,450.561],[252.043,440.864],[236.886,432.994],[217.673,428.701],[198.894,429.292],[166.031,436.453],[158.267,434.218],[150.287,428.616],[148.37,420.212],[153.228,412.647],[161.042,410.686],[169.002,415.003],[172.976,417.061],[204.811,415.615],[210.71,416.057],[216.435,415.125],[219.316,410.584],[221.025,406.764],[222.011,398.314],[221.3,394.915],[220.301,393.088],[217.016,390.94],[210.993,389.258],[206.782,388.894],[200.635,388.486],[195.446,388.553],[190.195,389.429],[185.254,391.401],[180.848,394.392],[177.204,398.246],[174.466,402.798],[172.028,410.329]];
const lakeBox = new THREE.Box3(new THREE.Vector3(148.3, -10, 376.3), new THREE.Vector3(307.1, 20, 539.2));

export function distanceToLakeShore(x, z) {
  let nearest = Infinity;
  for (let i = 1; i < LAKE_RING.length; i++) {
    const [ax, az] = LAKE_RING[i - 1], [bx, bz] = LAKE_RING[i];
    const dx = bx - ax, dz = bz - az;
    const t = THREE.MathUtils.clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1), 0, 1);
    nearest = Math.min(nearest, Math.hypot(x - ax - t * dx, z - az - t * dz));
  }
  return nearest;
}

export function lakeShoreTexture() {
  const size = 192, data = new Uint8Array(size * size);
  for (let z = 0; z < size; z++) for (let x = 0; x < size; x++) {
    const distance = distanceToLakeShore(148.3 + (x + .5) / size * 158.8, 376.3 + (z + .5) / size * 162.9);
    data[z * size + x] = Math.round(Math.min(distance / 12, 1) * 255);
  }
  // A tiny bank-distance field avoids wide false shallows across long source triangles.
  const texture = new THREE.DataTexture(data, size, size, THREE.RedFormat);
  texture.minFilter = texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;
  return texture;
}

function lakeWaterMaterial(time, shoreTexture) {
  const material = new THREE.MeshStandardMaterial({ name: 'Lake / interpretive calm water', color: '#47756b', roughness: .62, metalness: 0, side: THREE.DoubleSide, dithering: true });
  // A flat water sheet should receive shore shadows without casting onto itself.
  material.shadowSide = THREE.BackSide;
  material.onBeforeCompile = shader => {
    shader.uniforms.lakeTime = time;
    shader.uniforms.lakeShoreColor = { value: new THREE.Color('#74836f') };
    shader.uniforms.lakeShoreMap = { value: shoreTexture };
    shader.vertexShader = shader.vertexShader.replace('#include <common>', `#include <common>
      varying vec2 vLakeXZ;`).replace('#include <begin_vertex>', `#include <begin_vertex>
      vLakeXZ = (modelMatrix * vec4(transformed, 1.0)).xz;`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <common>', `#include <common>
      uniform float lakeTime;
      uniform vec3 lakeShoreColor;
      uniform sampler2D lakeShoreMap;
      varying vec2 vLakeXZ;`).replace('#include <color_fragment>', `#include <color_fragment>
      float shoreWidth = 2.0 + .25 * sin(vLakeXZ.x * .37 + vLakeXZ.y * .29);
      float shoreDistance = texture2D(lakeShoreMap, (vLakeXZ - vec2(148.3, 376.3)) / vec2(158.8, 162.9)).r * 12.0;
      float lakeShore = 1.0 - smoothstep(0.0, shoreWidth, shoreDistance);
      // A display transition at the mapped bank, not measured bathymetry.
      diffuseColor.rgb = mix(diffuseColor.rgb, lakeShoreColor, lakeShore * .45);`).replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
      roughnessFactor = mix(roughnessFactor, .68, lakeShore);`).replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
      float waveA = cos(dot(vLakeXZ, vec2(.72, .44)) + lakeTime * .45 + .6 * sin(vLakeXZ.y * .17));
      float waveB = cos(dot(vLakeXZ, vec2(-.41, .83)) - lakeTime * .33 + .4 * sin(vLakeXZ.x * .21));
      vec3 waveSlope = vec3(waveA * .018 - waveB * .009, 0.0, waveA * .009 + waveB * .014);
      normal = normalize(normal + mat3(viewMatrix) * waveSlope * faceDirection * (1.0 - lakeShore * .55));`);
  };
  material.customProgramCacheKey = () => 'lake-shore-ripples-v2';
  return material;
}

export function inLake(x, z, tolerance = .025) {
  if (x < 148.3 || x > 307.1 || z < 376.3 || z > 539.2) return false;
  let inside = false;
  for (let i = 1; i < LAKE_RING.length; i++) {
    const [ax, az] = LAKE_RING[i - 1], [bx, bz] = LAKE_RING[i];
    const dx = bx - ax, dz = bz - az;
    const t = THREE.MathUtils.clamp(((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz || 1), 0, 1);
    if (Math.hypot(x - ax - t * dx, z - az - t * dz) <= tolerance) return true;
    if ((az > z) !== (bz > z) && x < dx * (z - az) / dz + ax) inside = !inside;
  }
  return inside;
}

// Additional design planting, deliberately NOT associated with botanical POI IDs.
// Anchors exclude current site/building meshes and the sports infield; Y is terrain-raycast.
export const LAKE_PLANTING = {
  tall_tree: [[171,7.231,373],[301,9.434,373],[158,10.851,451],[314,8.488,477]],
  medium_tree: [[236,7.973,360],[145,8.9,386],[314,6.348,425],[301,6.044,529]],
  shrub: [[210,7.994,360],[171,7.987,386],[145,7.662,412],[186,5.250,437],[182,5.181,441],[301,7.005,477],[266,4.976,489],[301,4.436,516]],
  spreading: [[158,6.028,399],[286,6.942,545],[296,7.973,509]],
  slender: [[275,8.042,373],[314,6.403,399],[301,5.697,464],[314,8.261,503]],
};

/** Small reversible runtime patch; the Blender and exported GLBs remain unchanged. */
export class LakeEcologyVisuals {
  constructor() { this.enabled = true; this.models = new Map(); this.time = { value: 0 }; this.quality = 'high'; this.shoreTexture = null; }

  register(root) {
    if (this.models.has(root)) return;
    const entries = [];
    const isTerrain = root.userData.campusLayer === 'terrain';
    root.updateMatrixWorld(true);
    root.traverse(mesh => {
      if (!mesh.isMesh || Array.isArray(mesh.material)) return;
      const water = /water_calm_teal/.test(mesh.material.name);
      if (!water && !isTerrain) return;
      mesh.geometry.computeBoundingBox();
      if (!mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld).intersectsBox(lakeBox)) return;
      const original = mesh.geometry, position = original.attributes.position;
      const chosen = new Uint8Array(position.count), point = new THREE.Vector3();
      let count = 0;
      for (let i = 0; i < position.count; i++) {
        point.fromBufferAttribute(position, i).applyMatrix4(mesh.matrixWorld);
        if (point.y < 20 && inLake(point.x, point.z, water ? .025 : 0)) { chosen[i] = 1; count++; }
      }
      if (!count) return;
      const geometry = original.clone(), updated = geometry.attributes.position;
      const inverse = mesh.matrixWorld.clone().invert();
      for (let i = 0; i < position.count; i++) if (chosen[i]) {
        point.fromBufferAttribute(position, i).applyMatrix4(mesh.matrixWorld);
        point.y = water ? LAKE_LEVEL : Math.min(point.y, LAKE_LEVEL - .1);
        point.applyMatrix4(inverse);
        updated.setXYZ(i, point.x, point.y, point.z);
      }
      updated.needsUpdate = true;
      // GLB normals are normalized Int8; accumulating triangle areas into them overflows.
      geometry.deleteAttribute('normal');
      geometry.computeVertexNormals();
      // Preserve the original terrain/water shading outside the locally changed faces.
      const normalMask = water ? chosen : new Uint8Array(position.count);
      if (!water) {
        const index = original.index;
        for (let i = 0; i < (index?.count ?? position.count); i += 3) {
          const a = index ? index.getX(i) : i, b = index ? index.getX(i + 1) : i + 1, c = index ? index.getX(i + 2) : i + 2;
          if (updated.getY(a) !== position.getY(a) || updated.getY(b) !== position.getY(b) || updated.getY(c) !== position.getY(c)) normalMask[a] = normalMask[b] = normalMask[c] = 1;
        }
      }
      const sourceNormal = original.attributes.normal, normal = geometry.attributes.normal;
      for (let i = 0; i < position.count; i++) if (!normalMask[i]) normal.setXYZ(i, sourceNormal.getX(i), sourceNormal.getY(i), sourceNormal.getZ(i));
      geometry.computeBoundingBox(); geometry.computeBoundingSphere();
      let material = mesh.material;
      if (water) {
        const lake = [], other = [], index = original.index;
        for (let i = 0; i < (index?.count ?? position.count); i += 3) {
          const a = index ? index.getX(i) : i, b = index ? index.getX(i + 1) : i + 1, c = index ? index.getX(i + 2) : i + 2;
          (chosen[a] && chosen[b] && chosen[c] ? lake : other).push(a, b, c);
        }
        geometry.setIndex([...other, ...lake]);
        geometry.clearGroups();
        geometry.addGroup(0, other.length, 0);
        geometry.addGroup(other.length, lake.length, 1);
        this.shoreTexture ??= lakeShoreTexture();
        const lakeMaterial = lakeWaterMaterial(this.time, this.shoreTexture);
        material = [mesh.material, lakeMaterial];
      }
      entries.push({ mesh, original, geometry, originalMaterial: mesh.material, material, water, vertices: count });
    });
    this.models.set(root, entries);
    this.apply(entries);
  }

  apply(entries) {
    for (const entry of entries) {
      entry.mesh.geometry = this.enabled ? entry.geometry : entry.original;
      entry.mesh.material = this.enabled ? entry.material : entry.originalMaterial;
    }
  }

  setEnabled(value) { this.enabled = Boolean(value); for (const entries of this.models.values()) this.apply(entries); }

  setQuality(level) { this.quality = level; }

  update(elapsed, camera, animate = true) {
    if (!this.enabled || ![...this.models.values()].some(entries => entries.some(entry => entry.water))) return false;
    const moving = animate && this.quality !== 'low' && lakeBox.distanceToPoint(camera.position) < 650;
    const next = moving ? elapsed : 0;
    const changed = this.time.value !== next;
    this.time.value = next;
    return changed;
  }

  unregister(root) {
    for (const entry of this.models.get(root) || []) {
      entry.mesh.geometry = entry.original; entry.mesh.material = entry.originalMaterial;
      entry.geometry.dispose(); if (entry.water) entry.material[1].dispose();
    }
    this.models.delete(root);
  }

  dispose() { for (const root of [...this.models.keys()]) this.unregister(root); this.shoreTexture?.dispose(); this.shoreTexture = null; }
}
