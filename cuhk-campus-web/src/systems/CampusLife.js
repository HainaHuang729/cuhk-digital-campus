import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { LakeEcologyVisuals, LAKE_PLANTING } from './LakeEcologyVisuals.js';

const QUALITY = {
  high: { people: 24, near: 650, treeStride: 1, motionRange: 650 },
  medium: { people: 16, near: 420, treeStride: 1, motionRange: 500 },
  low: { people: 10, near: 220, treeStride: 2, motionRange: 350 },
};
const WIND = `
float bend = pow(clamp(position.y, 0.0, 1.15), 2.0);
float phase = campusWindTime * 0.8 + instanceMatrix[3].x * 0.021 + instanceMatrix[3].z * 0.017;
transformed.x += sin(phase) * bend * 0.016;
transformed.z += cos(phase * 0.73) * bend * 0.009;
`;

function windMaterial(material, uniform) {
  material.onBeforeCompile = shader => {
    shader.uniforms.campusWindTime = uniform;
    shader.vertexShader = 'uniform float campusWindTime;\n' + shader.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n' + WIND);
  };
  material.customProgramCacheKey = () => 'campus-tree-wind-v1';
  return material;
}

function preparePath(path) {
  const points = path.points.map(point => new THREE.Vector3(...point));
  const distances = [0];
  for (let i = 1; i < points.length; i++) distances.push(distances.at(-1) + points[i].distanceTo(points[i - 1]));
  return { ...path, points, distances, length: distances.at(-1) };
}

// Linear sampling preserves the surveyed road bends: splines could cut across a hillside.
export function samplePath(path, distance, position, direction) {
  const cycle = ((distance % (2 * path.length)) + 2 * path.length) % (2 * path.length);
  const forward = cycle < path.length;
  const at = forward ? cycle : 2 * path.length - cycle;
  let low = 0, high = path.distances.length - 1;
  while (low + 1 < high) {
    const mid = (low + high) >> 1;
    if (path.distances[mid] <= at) low = mid; else high = mid;
  }
  const a = path.points[low], b = path.points[low + 1];
  position.lerpVectors(a, b, (at - path.distances[low]) / Math.max(.0001, path.distances[low + 1] - path.distances[low]));
  direction.subVectors(b, a).normalize().multiplyScalar(forward ? 1 : -1);
  return forward;
}

function coloredGeometry(parts) {
  const geometries = parts.map(([geometry, color, position = [0, 0, 0], rotation = [0, 0, 0]]) => {
    const g = geometry.index ? geometry.toNonIndexed() : geometry.clone();
    const matrix = new THREE.Matrix4().compose(new THREE.Vector3(...position), new THREE.Quaternion().setFromEuler(new THREE.Euler(...rotation)), new THREE.Vector3(1, 1, 1));
    g.applyMatrix4(matrix);
    const c = new THREE.Color(color), colors = new Float32Array(g.attributes.position.count * 3);
    for (let i = 0; i < colors.length; i += 3) c.toArray(colors, i);
    g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    g.deleteAttribute('uv');
    geometry.dispose();
    return g;
  });
  const result = mergeGeometries(geometries);
  for (const geometry of geometries) geometry.dispose();
  return result;
}

function carGeometry() {
  const parts = [
    [new THREE.BoxGeometry(1.62, .60, 3.65), '#aab8b0', [0, .68, 0]],
    [new THREE.BoxGeometry(1.42, .62, 1.9), '#899d9b', [0, 1.22, -.12]],
    [new THREE.BoxGeometry(1.44, .38, 1.6), '#263d46', [0, 1.27, -.12]],
    [new THREE.BoxGeometry(1.2, .14, .05), '#dbc69a', [0, .77, 1.85]],
  ];
  for (const x of [-.79, .79]) for (const z of [-1.13, 1.13]) parts.push([new THREE.CylinderGeometry(.30, .30, .18, 8), '#283032', [x, .33, z], [0, 0, Math.PI / 2]]);
  return coloredGeometry(parts);
}

function bicycleGeometry(rider = true) {
  const parts = [];
  for (const z of [-.61, .61]) parts.push([new THREE.TorusGeometry(.34, .035, 4, 12), '#334044', [0, .38, z], [0, Math.PI / 2, 0]]);
  const points = [[0, .38, -.61], [0, .42, 0], [0, 1.0, -.19], [0, .91, .43], [0, .38, .61]];
  for (const [a, b] of [[0,1],[1,2],[0,2],[2,3],[1,3],[3,4]]) {
    const start = new THREE.Vector3(...points[a]), end = new THREE.Vector3(...points[b]);
    const geometry = new THREE.CylinderGeometry(.027, .027, start.distanceTo(end), 5);
    const quaternion = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), end.clone().sub(start).normalize());
    geometry.applyQuaternion(quaternion);
    parts.push([geometry, '#ae9e79', start.lerp(end, .5).toArray()]);
  }
  parts.push([new THREE.BoxGeometry(.29, .07, .22), '#364049', [0, 1.04, -.19]]);
  parts.push([new THREE.BoxGeometry(.62, .045, .05), '#364049', [0, 1.03, .43]]);
  // A quiet architectural silhouette, without skeletal character assets.
  if (rider) {
    parts.push([new THREE.BoxGeometry(.36, .50, .25), '#788e92', [0, 1.38, -.07], [.23, 0, 0]]);
    parts.push([new THREE.IcosahedronGeometry(.135, 0), '#bfab91', [0, 1.74, .05]]);
    for (const x of [-.13, .13]) parts.push([new THREE.BoxGeometry(.12, .48, .16), '#34434a', [x, .85, -.05], [.3, 0, 0]]);
  }
  return coloredGeometry(parts);
}

function benchGeometry() {
  const parts = [
    [new THREE.BoxGeometry(1.68, .085, .48), '#9d8b6e', [0, .47, 0]],
    [new THREE.BoxGeometry(1.68, .33, .07), '#9d8b6e', [0, .76, -.25]],
  ];
  for (const x of [-.59, .59]) for (const z of [-.18, .18]) parts.push([new THREE.BoxGeometry(.07, .74, .07), '#45534f', [x, .22, z]]);
  return coloredGeometry(parts);
}

function binGeometry() {
  return coloredGeometry([
    [new THREE.CylinderGeometry(.20, .18, .76, 8), '#52645b', [0, .38, 0]],
    [new THREE.CylinderGeometry(.215, .20, .10, 8), '#3a4643', [0, .81, 0]],
    [new THREE.BoxGeometry(.21, .105, .035), '#22332f', [0, .78, .195]],
  ]);
}

export function plantGeometry(type) {
  const foliage = { tall_tree: '#597d52', medium_tree: '#76945c', shrub: '#668652', spreading: '#70995f', slender: '#49765b' }[type];
  // Shared silhouettes stay inside the original planting envelopes, not species reconstructions.
  const crowns = {
    tall_tree: [[-.19,.72,-.08,.21,.23,.20],[.13,.70,.14,.23,.20,.21],[.24,.85,-.11,.19,.20,.18],[-.17,.92,.12,.19,.17,.18],[.05,.99,-.05,.20,.15,.19],[-.30,.79,.12,.15,.16,.15]],
    medium_tree: [[-.19,.63,.04,.17,.20,.18],[.17,.67,-.10,.20,.19,.18],[.12,.85,.13,.18,.17,.19],[-.11,.90,-.07,.20,.15,.18],[-.24,.79,-.09,.14,.16,.16]],
    shrub: [[-.28,.30,-.10,.24,.22,.22],[.18,.35,-.12,.26,.29,.24],[.33,.44,.14,.20,.25,.21],[-.16,.55,.15,.24,.23,.23],[.07,.57,.01,.21,.20,.20]],
    spreading: [[-.43,.67,-.07,.24,.16,.24],[.38,.73,.04,.27,.16,.25],[-.16,.83,.23,.26,.16,.22],[.12,.86,-.23,.24,.17,.25],[-.18,.73,-.26,.23,.15,.22],[.03,.94,.05,.23,.13,.24],[.47,.65,-.18,.18,.12,.19]],
    slender: [[-.08,.40,.02,.12,.18,.14],[.06,.51,-.03,.16,.18,.15],[-.06,.63,.06,.15,.20,.14],[.05,.73,-.07,.14,.17,.14],[-.06,.86,-.02,.12,.17,.13],[.03,.97,.04,.10,.15,.11],[.00,1.07,-.02,.065,.10,.075]],
  }[type];
  const parts = [];
  const branch = (start, end, radius) => {
    const a = new THREE.Vector3(...start), b = new THREE.Vector3(...end);
    const geometry = new THREE.CylinderGeometry(radius * .48, radius, a.distanceTo(b), 5);
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(THREE.Object3D.DEFAULT_UP, b.clone().sub(a).normalize()));
    parts.push([geometry, '#796650', a.lerp(b, .5).toArray()]);
  };
  if (type !== 'shrub') {
    branch([0,0,0], [.015,.39,-.018], .034);
    branch([.015,.39,-.018], [.035,type === 'slender' ? 1.04 : .67,.005], .024);
  }
  for (const [index, [x,y,z,sx,sy,sz]] of crowns.entries()) {
    const crown = new THREE.IcosahedronGeometry(1, 1), position = crown.attributes.position;
    for (let i = 0; i < position.count; i++) {
      const px = position.getX(i), py = position.getY(i), pz = position.getZ(i);
      const ripple = 1 + .09 * Math.sin(px * 5 + py * 3 + index) * Math.cos(pz * 6 - py * 2);
      position.setXYZ(i, px * ripple, py * ripple, pz * ripple);
    }
    crown.scale(sx, sy, sz);
    const tone = new THREE.Color(foliage).multiplyScalar(.91 + (index % 3) * .07);
    parts.push([crown, tone, [x,y,z]]);
    if (type !== 'shrub') branch([.015,type === 'slender' ? y - .18 : .36,-.018], [x,y,z], .012);
  }
  const geometry = coloredGeometry(parts), colors = geometry.attributes.color;
  const position = geometry.attributes.position, normal = geometry.attributes.normal;
  for (let i = 0; i < colors.count; i++) {
    // Foliage reads as layered masses; branch colour keeps its existing matte finish.
    if (colors.getY(i) > colors.getX(i) * 1.1) {
      const shade = .84 + .16 * THREE.MathUtils.clamp(position.getY(i), 0, 1.2) + .065 * normal.getY(i);
      colors.setXYZ(i, colors.getX(i) * shade, colors.getY(i) * shade, colors.getZ(i) * shade);
    }
  }
  return geometry;
}

export function sampleLakeBird(elapsed, index, position) {
  const angle = elapsed * .10 + index * .20;
  // Illustrative flight around the mapped lake, not tracked animals or a species claim.
  return position.set(237 + Math.sin(angle) * 60, 27 + Math.sin(angle * 2) * 5 + index * .65, 422 + Math.cos(angle) * 28);
}

export class CampusLife {
  constructor({ scene, loader, requestRender = () => {} }) {
    this.scene = scene;
    this.loader = loader;
    this.requestRender = requestRender;
    this.group = new THREE.Group();
    this.group.name = 'Campus Life / illustrative activity';
    this.scene.add(this.group);
    this.wind = { value: 0 };
    this.quality = QUALITY.high;
    this.peopleEnabled = true;
    this.vegetationEnabled = true;
    this.ready = false;
    this.nightAmount = 0;
    this.lastCull = -Infinity;
    this.lastCamera = new THREE.Vector3(Infinity, Infinity, Infinity);
    this.lastQuaternion = new THREE.Quaternion();
    this.lastProjection = new THREE.Matrix4();
    this.scratch = new THREE.Object3D();
    this.position = new THREE.Vector3();
    this.direction = new THREE.Vector3();
    this.frustum = new THREE.Frustum();
    this.projection = new THREE.Matrix4();
    this.sphere = new THREE.Sphere(new THREE.Vector3(), 16);
    this.resources = new Set();
    this.lakeVisuals = new LakeEcologyVisuals();
    this.ecologyVisualsEnabled = true;
  }

  mesh(geometry, material, count, name, shadow = true) {
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    mesh.name = name;
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    mesh.castShadow = shadow;
    mesh.receiveShadow = true;
    // Instance lists are culled explicitly, and move every frame.
    mesh.frustumCulled = false;
    mesh.count = 0;
    this.group.add(mesh);
    this.resources.add(geometry);
    this.resources.add(material);
    return mesh;
  }

  async load() {
    const response = await fetch('/campus/life.json');
    if (!response.ok) throw new Error('Campus activity data failed to load');
    const data = await response.json();
    const vegetation = await this.loader.loadAsync('/campus/vegetation.glb');
    this.paths = data.paths.map(preparePath);
    this.trees = data.treeInstances.map(row => ({ template: row[0], matrix: new THREE.Matrix4().fromArray(row.slice(1)), position: new THREE.Vector3(row[13], row[14], row[15]) }));
    const depth = windMaterial(new THREE.MeshDepthMaterial({ depthPacking: THREE.RGBADepthPacking, side: THREE.DoubleSide }), this.wind);
    this.resources.add(depth);
    this.treeMeshes = data.treeTemplates.map((entry, index) => ['near', 'far'].map(lod => {
      const source = vegetation.scene.getObjectByName(entry[lod]);
      if (!source?.isMesh) throw new Error(`Missing tree template ${entry[lod]}`);
      const material = windMaterial(source.material.clone(), this.wind);
      material.side = THREE.DoubleSide;
      const mesh = this.mesh(source.geometry, material, this.trees.filter(t => t.template === index).length, `Trees ${index} ${lod}`);
      mesh.customDepthMaterial = depth;
      return mesh;
    }));
    vegetation.scene.traverse(object => { if (object.isMesh) object.material.dispose(); });
    this.lakePlantMeshes = Object.entries(LAKE_PLANTING).map(([type, positions]) => {
      const material = windMaterial(new THREE.MeshStandardMaterial({ name: `Lake planting / ${type}`, vertexColors: true, roughness: .95 }), this.wind);
      const mesh = this.mesh(plantGeometry(type), material, positions.length, `Lake illustrative planting / ${type}`);
      mesh.userData = { visualType: type, locationConfidence: 'inferred', botanicalInventory: false };
      mesh.customDepthMaterial = depth;
      const height = { tall_tree: 11.5, medium_tree: 7.5, shrub: 2, spreading: 7, slender: 12 }[type];
      for (const [index, position] of positions.entries()) this.place(mesh, index, new THREE.Vector3(...position), index * .87, [0, 0, 0], 0, height * (1 + (index % 3 - 1) * .08));
      mesh.count = positions.length;
      mesh.instanceMatrix.needsUpdate = true;
      mesh.frustumCulled = true;
      mesh.computeBoundingSphere();
      mesh.visible = this.ecologyVisualsEnabled && this.vegetationEnabled;
      return mesh;
    });
    const cloth = new THREE.MeshStandardMaterial({ color: '#ffffff', roughness: .9 });
    const dark = new THREE.MeshStandardMaterial({ color: '#3b4850', roughness: .94 });
    const skin = new THREE.MeshStandardMaterial({ color: '#bea990', roughness: .9 });
    this.peopleMeshes = {
      bodies: this.mesh(new THREE.BoxGeometry(.40, .56, .25), cloth, 24, 'People / coats'),
      heads: this.mesh(new THREE.IcosahedronGeometry(.15, 1), skin, 24, 'People / heads'),
      arms: this.mesh(new THREE.BoxGeometry(.105, .52, .115), cloth, 48, 'People / walking arms'),
      legs: this.mesh(new THREE.BoxGeometry(.13, .72, .16), dark, 48, 'People / walking legs'),
    };
    const palette = ['#738b92', '#ad9b83', '#856b68', '#6e7870', '#d0c6b1', '#6d7f93'];
    for (let i = 0; i < 24; i++) {
      const color = new THREE.Color(palette[i % palette.length]);
      this.peopleMeshes.bodies.setColorAt(i, color);
      this.peopleMeshes.arms.setColorAt(i * 2, color);
      this.peopleMeshes.arms.setColorAt(i * 2 + 1, color);
    }
    const vehicleMaterial = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .65 });
    this.cars = this.mesh(carGeometry(), vehicleMaterial, 2, 'Campus cars');
    this.bicycles = this.mesh(bicycleGeometry(), vehicleMaterial, 2, 'Campus cyclists');
    this.furniture = [];
    for (const [kind, geometry] of [['benches', benchGeometry()], ['bins', binGeometry()], ['bicycles', bicycleGeometry(false)]]) {
      const rows = data.furniture?.[kind] || [];
      const mesh = this.mesh(geometry, vehicleMaterial, Math.max(1, rows.length), `Illustrative path-side ${kind}`);
      for (const [index, row] of rows.entries()) this.place(mesh, index, new THREE.Vector3(...row.position), row.yaw, [0, 0, 0]);
      mesh.count = rows.length;
      mesh.instanceMatrix.needsUpdate = true;
      this.furniture.push(mesh);
    }
    const poolMaterial = new THREE.ShaderMaterial({
      uniforms: { nightAmount: { value: this.nightAmount } },
      vertexShader: 'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*instanceMatrix*vec4(position,1.0);}',
      fragmentShader: 'varying vec2 vUv; uniform float nightAmount; void main(){float radius=length(vUv-.5)*2.0;float soft=pow(max(0.0,1.0-radius),2.0);gl_FragColor=vec4(1.0,.76,.40,soft*nightAmount*.33);}',
      transparent: true, blending: THREE.AdditiveBlending, depthTest: true, depthWrite: false,
      side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1,
    });
    const pools = data.lampPools || [];
    this.lampPools = this.mesh(new THREE.CircleGeometry(1, 24).rotateX(-Math.PI / 2), poolMaterial, Math.max(1, pools.length), 'Existing lamps / soft ground glow', false);
    for (const [index, matrix] of pools.entries()) this.lampPools.setMatrixAt(index, new THREE.Matrix4().fromArray(matrix));
    this.lampPools.count = pools.length;
    this.lampPools.instanceMatrix.needsUpdate = true;
    this.lampPools.visible = this.nightAmount > .02;
    const wing = new THREE.BufferGeometry();
    wing.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, .18, 0, 0, -.22, .7, 0, -.08], 3));
    wing.computeVertexNormals();
    this.birds = this.mesh(wing, new THREE.MeshStandardMaterial({ color: '#425359', roughness: .95, side: THREE.DoubleSide }), 12, 'Distant birds', false);
    this.actors = Array.from({ length: 24 }, (_, i) => ({ path: this.paths.filter(p => p.kind === 'walk')[i % 6], offset: i * 37.13, yaw: null }));
    this.ready = true;
    this.requestRender();
  }

  place(mesh, index, position, yaw, offset, rotation = 0, scale = 1) {
    const object = this.scratch;
    object.position.set(...offset).applyAxisAngle(THREE.Object3D.DEFAULT_UP, yaw).add(position);
    object.rotation.set(rotation, yaw, 0, 'YXZ');
    object.scale.setScalar(scale);
    object.updateMatrix();
    mesh.setMatrixAt(index, object.matrix);
  }

  cullTrees(camera, elapsed) {
    if (this.lastCull !== -Infinity && camera.position.equals(this.lastCamera)
      && camera.quaternion.equals(this.lastQuaternion) && camera.projectionMatrix.equals(this.lastProjection)) return false;
    this.lastCull = elapsed;
    this.lastCamera.copy(camera.position);
    this.lastQuaternion.copy(camera.quaternion);
    this.lastProjection.copy(camera.projectionMatrix);
    camera.updateMatrixWorld();
    this.projection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.projection);
    for (const meshes of this.treeMeshes) for (const mesh of meshes) mesh.count = 0;
    if (this.vegetationEnabled) for (let i = 0; i < this.trees.length; i += this.quality.treeStride) {
      const tree = this.trees[i];
      this.sphere.center.copy(tree.position).y += 5;
      if (!this.frustum.intersectsSphere(this.sphere)) continue;
      const distance = camera.position.distanceTo(tree.position);
      if (distance > 5300) continue;
      const lod = distance < this.quality.near ? 0 : 1;
      const mesh = this.treeMeshes[tree.template][lod];
      mesh.setMatrixAt(mesh.count++, tree.matrix);
    }
    for (const meshes of this.treeMeshes) for (const mesh of meshes) {
      mesh.visible = mesh.count > 0;
      mesh.instanceMatrix.needsUpdate = true;
    }
    return true;
  }

  update(elapsed, delta, camera, animate = true) {
    if (!this.ready) return false;
    const culled = this.cullTrees(camera, elapsed);
    const lakeChanged = this.lakeVisuals.update(elapsed, camera, animate);
    if (!animate) { elapsed = 0; delta = 0; }
    this.wind.value = elapsed;
    let count = 0;
    const meshes = this.peopleMeshes;
    if (this.peopleEnabled) for (let i = 0; i < this.quality.people; i++) {
      const actor = this.actors[i];
      samplePath(actor.path, elapsed * (1.03 + i % 4 * .09) + actor.offset, this.position, this.direction);
      if (camera.position.distanceTo(this.position) > this.quality.motionRange) continue;
      const wanted = Math.atan2(this.direction.x, this.direction.z);
      if (actor.yaw === null) actor.yaw = wanted;
      actor.yaw += Math.atan2(Math.sin(wanted - actor.yaw), Math.cos(wanted - actor.yaw)) * Math.min(1, delta * 8);
      const swing = Math.sin(elapsed * (6.8 + i % 3 * .25) + i) * .36;
      const bob = Math.abs(Math.sin(elapsed * 6.8 + i)) * .025;
      this.place(meshes.bodies, count, this.position, actor.yaw, [0, 1.08 + bob, 0]);
      this.place(meshes.heads, count, this.position, actor.yaw, [0, 1.53 + bob, 0]);
      for (const side of [-1, 1]) {
        const limb = count * 2 + (side === 1 ? 1 : 0);
        this.place(meshes.arms, limb, this.position, actor.yaw, [side * .26, 1.05 + bob, 0], -side * swing);
        this.place(meshes.legs, limb, this.position, actor.yaw, [side * .11, .39, -side * Math.sin(swing) * .18], side * swing);
      }
      count++;
    }
    meshes.bodies.count = meshes.heads.count = count;
    meshes.arms.count = meshes.legs.count = count * 2;
    for (const mesh of Object.values(meshes)) mesh.instanceMatrix.needsUpdate = true;
    for (const [mesh, kind, speed] of [[this.cars, 'vehicle', 5.5], [this.bicycles, 'cycle', 3.8]]) {
      mesh.count = 0;
      if (!this.peopleEnabled) continue;
      const paths = this.paths.filter(path => path.kind === kind);
      for (let i = 0; i < 2; i++) {
        samplePath(paths[i % paths.length], elapsed * speed + i * 187, this.position, this.direction);
        if (camera.position.distanceTo(this.position) > this.quality.motionRange + 150) continue;
        const yaw = Math.atan2(this.direction.x, this.direction.z);
        this.place(mesh, mesh.count++, this.position, yaw, [kind === 'vehicle' ? -.70 : -.24, 0, 0], -Math.asin(THREE.MathUtils.clamp(this.direction.y, -.4, .4)));
      }
      mesh.instanceMatrix.needsUpdate = true;
    }
    this.birds.count = 0;
    if (this.peopleEnabled && this.quality !== QUALITY.low && (!this.ecologyVisualsEnabled || this.nightAmount < .65)) for (let i = 0; i < 6; i++) {
      const angle = this.ecologyVisualsEnabled ? elapsed * .10 + i * .20 : elapsed * .045 + i * .07;
      if (this.ecologyVisualsEnabled) sampleLakeBird(elapsed, i, this.position);
      else this.position.set(230 + Math.sin(angle) * 140 + i * 6, 210 + Math.sin(angle * 2) * 8 + i * 2, -90 + Math.cos(angle) * 105);
      if (this.ecologyVisualsEnabled && camera.position.distanceTo(this.position) > 800) continue;
      for (const side of [-1, 1]) {
        const object = this.scratch;
        object.position.copy(this.position);
        const yaw = this.ecologyVisualsEnabled ? Math.atan2(Math.cos(angle) * 60, -Math.sin(angle) * 28) : angle + Math.PI / 2;
        object.rotation.set(0, yaw, side * Math.sin(elapsed * 5 + i) * .5, 'YXZ');
        object.scale.set(side, 1, 1);
        object.updateMatrix();
        this.birds.setMatrixAt(this.birds.count++, object.matrix);
      }
    }
    this.birds.instanceMatrix.needsUpdate = true;
    return culled || lakeChanged || (animate && (this.peopleEnabled || this.vegetationEnabled));
  }

  setQuality(level) { this.quality = QUALITY[String(level).toLowerCase()] || QUALITY.high; this.lakeVisuals.setQuality(level); this.lastCull = -Infinity; this.requestRender(); }
  setPeopleEnabled(value) { this.peopleEnabled = Boolean(value); this.requestRender(); }
  setVegetationEnabled(value) {
    this.vegetationEnabled = Boolean(value);
    for (const mesh of this.lakePlantMeshes || []) mesh.visible = this.vegetationEnabled && this.ecologyVisualsEnabled;
    this.lastCull = -Infinity; this.requestRender();
  }
  registerLakeModel(root) { this.lakeVisuals.register(root); this.requestRender(); }
  unregisterLakeModel(root) { this.lakeVisuals.unregister(root); }
  setEcologyVisualsEnabled(value) {
    this.ecologyVisualsEnabled = Boolean(value);
    this.lakeVisuals.setEnabled(this.ecologyVisualsEnabled);
    for (const mesh of this.lakePlantMeshes || []) mesh.visible = this.vegetationEnabled && this.ecologyVisualsEnabled;
    this.requestRender();
  }
  setNightAmount(value) {
    this.nightAmount = THREE.MathUtils.clamp(value, 0, 1);
    if (this.lampPools) {
      this.lampPools.material.uniforms.nightAmount.value = this.nightAmount;
      this.lampPools.visible = this.nightAmount > .02;
    }
    this.requestRender();
  }
  getStats() {
    const meshes = this.group.children.filter(child => child.isInstancedMesh && child.visible && child.count);
    return { illustrative: true, people: this.peopleMeshes?.bodies.count || 0, cars: this.cars?.count || 0, bicycles: this.bicycles?.count || 0,
      trees: this.treeMeshes?.flat().reduce((sum, mesh) => sum + mesh.count, 0) || 0,
      lakePlanting: this.lakePlantMeshes?.reduce((sum, mesh) => sum + (mesh.visible ? mesh.count : 0), 0) || 0,
      lakeVisuals: this.ecologyVisualsEnabled,
      furniture: this.furniture?.reduce((sum, mesh) => sum + mesh.count, 0) || 0,
      nightPools: this.lampPools?.visible ? this.lampPools.count : 0,
      drawCalls: meshes.length, triangles: meshes.reduce((sum, mesh) => sum + (mesh.geometry.index?.count ?? mesh.geometry.attributes.position.count) / 3 * mesh.count, 0) };
  }
  dispose() { this.lakeVisuals.dispose(); this.scene.remove(this.group); for (const resource of this.resources) resource.dispose(); this.group.clear(); this.ready = false; }
}
