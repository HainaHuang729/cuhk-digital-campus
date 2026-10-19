import * as THREE from 'three';

const KEYFRAMES = [
  // hour, zenith, horizon, sun, sky fill, ground fill, sun intensity, fill intensity, environment, exposure, night
  [0, '#091426', '#26354c', '#becfe9', '#93afd6', '#1c2634', 0, .28, .16, .8, 1],
  [5.3, '#142b48', '#697b91', '#becfe9', '#9ab4d5', '#39424a', 0, .4, .18, .88, .9],
  [6.3, '#6685a0', '#d7c5b4', '#ffdab1', '#d0ddef', '#858775', .15, .75, .24, .96, .4],
  [8.5, '#799eb9', '#dce4e0', '#fff0da', '#e3edfa', '#929882', 2.45, 1.1, .28, 1, 0],
  [12, '#7299b4', '#dce5df', '#fff7eb', '#e5effb', '#929984', 2.8, 1.22, .3, .98, 0],
  [16.5, '#8da5b6', '#e6ddce', '#ffdfb2', '#e4e7ed', '#958573', 2.25, 1.02, .28, 1.02, 0],
  [18, '#667d9d', '#e3b48d', '#ffb875', '#c0cce2', '#79675c', .95, .67, .23, 1.05, .3],
  [19.3, '#1b3355', '#6b7292', '#9caed5', '#93aed8', '#353c4a', 0, .35, .18, .9, .92],
  [21, '#091426', '#26354c', '#becfe9', '#93afd6', '#1c2634', 0, .28, .16, .8, 1],
  [24, '#091426', '#26354c', '#becfe9', '#93afd6', '#1c2634', 0, .28, .16, .8, 1],
].map(([hour, zenith, horizon, sun, sky, ground, sunIntensity, fillIntensity, environment, exposure, nightAmount]) => ({
  hour, zenith: new THREE.Color(zenith), horizon: new THREE.Color(horizon), sun: new THREE.Color(sun),
  sky: new THREE.Color(sky), ground: new THREE.Color(ground), sunIntensity, fillIntensity, environment, exposure, nightAmount,
}));

export function sampleTimeOfDay(value) {
  const hours = Number.isFinite(value) ? THREE.MathUtils.euclideanModulo(value, 24) : 12;
  const index = KEYFRAMES.findIndex(frame => frame.hour > hours);
  const a = KEYFRAMES[index - 1];
  const b = KEYFRAMES[index];
  const t = THREE.MathUtils.smoothstep(hours, a.hour, b.hour);
  const state = { hours };
  for (const name of ['zenith', 'horizon', 'sun', 'sky', 'ground']) state[name] = a[name].clone().lerp(b[name], t);
  for (const name of ['sunIntensity', 'fillIntensity', 'environment', 'exposure', 'nightAmount']) state[name] = THREE.MathUtils.lerp(a[name], b[name], t);
  // A readable equinox-like campus cycle, not an astronomical sun-position service.
  const angle = (hours - 6.3) / 12 * Math.PI;
  state.sunDirection = new THREE.Vector3(Math.cos(angle), Math.sin(angle) * 1.65, .35).normalize();
  state.sunElevation = Math.asin(state.sunDirection.y) * THREE.MathUtils.RAD2DEG;
  state.sunIntensity *= THREE.MathUtils.smoothstep(state.sunDirection.y, -.02, .12);
  state.status = state.nightAmount > .8 ? 'NIGHT' : hours < 8.5 ? 'DAWN' : hours >= 16.5 ? 'GOLDEN HOUR' : 'CLEAR';
  return state;
}

export class TimeOfDaySystem {
  constructor({ scene, renderer, sun, fill, requestRender = () => {} }) {
    Object.assign(this, { scene, renderer, sun, fill, requestRender });
    this.materials = new Map();
    this.models = new Map();
    this.target = new THREE.Vector3(0, 60, 0);
    this.direction = new THREE.Vector3();
    this.shadowDirection = new THREE.Vector3();
    this.overrides = { exposure: 1, fog: 1, environment: 1, sunAzimuth: 0, shadows: true };
    this.playing = false;
    this.speed = .16; // Campus hours per real second when playback is enabled.
    this.quality = 'medium';
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(8000, 32, 16), new THREE.ShaderMaterial({
      name: 'Campus sky gradient', side: THREE.BackSide, depthWrite: false, depthTest: false,
      uniforms: { zenith: { value: new THREE.Color() }, horizon: { value: new THREE.Color() } },
      vertexShader: `varying vec3 skyDirection;
        void main() {
          skyDirection = position;
          vec4 clip = projectionMatrix * mat4(mat3(viewMatrix)) * vec4(position, 1.0);
          gl_Position = clip.xyww;
        }`,
      fragmentShader: `uniform vec3 zenith; uniform vec3 horizon; varying vec3 skyDirection;
        void main() {
          float height = clamp(normalize(skyDirection).y, 0.0, 1.0);
          gl_FragColor = vec4(mix(horizon, zenith, pow(height, 0.62)), 1.0);
          #include <tonemapping_fragment>
          #include <colorspace_fragment>
        }`,
    }));
    this.sky.name = 'Campus atmosphere';
    this.sky.renderOrder = -1000;
    this.sky.frustumCulled = false;
    this.sky.userData.isAtmosphere = true;
    scene.add(this.sky);
    scene.fog = new THREE.Fog('#dce5df', 2400, 6800);
    sun.shadow.autoUpdate = false;
    this.setTime(17.7);
  }

  setTime(hours) {
    this.state = sampleTimeOfDay(hours);
    this.apply();
    return this.state;
  }

  setPlaying(value) { this.playing = Boolean(value); }

  update(deltaSeconds) {
    if (!this.playing || !Number.isFinite(deltaSeconds) || deltaSeconds <= 0) return false;
    this.setTime(this.state.hours + Math.min(deltaSeconds, .1) * this.speed);
    return true;
  }

  setOverrides(values) {
    for (const key of ['exposure', 'fog', 'environment']) {
      if (Number.isFinite(values[key])) this.overrides[key] = THREE.MathUtils.clamp(values[key], key === 'exposure' ? .25 : 0, 3);
    }
    if (Number.isFinite(values.sunAzimuth)) this.overrides.sunAzimuth = values.sunAzimuth;
    if (typeof values.shadows === 'boolean') this.overrides.shadows = values.shadows;
    this.apply();
  }

  apply() {
    const state = this.state;
    const overrides = this.overrides;
    this.sun.color.copy(state.sun);
    this.sun.intensity = state.sunIntensity;
    this.fill.color.copy(state.sky);
    this.fill.groundColor.copy(state.ground);
    this.fill.intensity = state.fillIntensity;
    this.scene.environmentIntensity = state.environment * overrides.environment;
    this.renderer.toneMappingExposure = state.exposure * overrides.exposure;
    this.scene.background = state.horizon;
    this.scene.fog.color.copy(state.horizon);
    this.scene.fog.near = overrides.fog > 0 ? 2400 / overrides.fog : 20000;
    this.scene.fog.far = overrides.fog > 0 ? (6800 - state.nightAmount * 1200) / overrides.fog : 30000;
    this.sky.material.uniforms.zenith.value.copy(state.zenith);
    this.sky.material.uniforms.horizon.value.copy(state.horizon);
    this.direction.copy(state.sunDirection).applyAxisAngle(THREE.Object3D.DEFAULT_UP, overrides.sunAzimuth * THREE.MathUtils.DEG2RAD);
    this.sun.target.position.copy(this.target);
    this.sun.position.copy(this.target).addScaledVector(this.direction, 1900);
    const shadowSettingChanged = this.renderer.shadowMap.enabled !== overrides.shadows;
    this.renderer.shadowMap.enabled = overrides.shadows;
    for (const [material, entry] of this.materials) this.updateMaterial(material, entry);
    this.invalidateShadow(shadowSettingChanged);
    this.requestRender();
  }

  updateMaterial(material, entry) {
    if (!entry.kind) return;
    const amount = THREE.MathUtils.smoothstep(this.state.nightAmount, .1, .9);
    material.emissive.copy(entry.color).lerp(entry.kind === 'lamp' ? LAMP_COLOR : WINDOW_COLOR, amount);
    material.emissiveIntensity = THREE.MathUtils.lerp(entry.intensity, entry.kind === 'lamp' ? 2 : .56, amount);
  }

  registerModel(root) {
    if (this.models.has(root)) return () => this.unregisterModel(root);
    const materials = new Set();
    root.traverse(object => {
      if (!object.isMesh) return;
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) materials.add(material);
    });
    this.models.set(root, materials);
    for (const material of materials) {
      let entry = this.materials.get(material);
      if (!entry) {
        const kind = material.emissive && (/lamp_heads/i.test(material.name) ? 'lamp' : /glazing|glass/i.test(material.name) ? 'window' : null);
        entry = { count: 0, kind, color: material.emissive?.clone(), intensity: material.emissiveIntensity ?? 1, environment: material.envMapIntensity };
        this.materials.set(material, entry);
        // The scene controls environment brightness once; avoid multiplying it by .3 a second time.
        if ('envMapIntensity' in material) material.envMapIntensity = 1;
      }
      entry.count++;
      this.updateMaterial(material, entry);
    }
    this.invalidateShadow();
    this.requestRender();
    return () => this.unregisterModel(root);
  }

  unregisterModel(root) {
    const materials = this.models.get(root);
    if (!materials) return;
    for (const material of materials) {
      const entry = this.materials.get(material);
      if (--entry.count > 0) continue;
      if (entry.kind) { material.emissive.copy(entry.color); material.emissiveIntensity = entry.intensity; }
      if (entry.environment !== undefined) material.envMapIntensity = entry.environment;
      this.materials.delete(material);
    }
    this.models.delete(root);
    this.invalidateShadow();
    this.requestRender();
  }

  invalidateShadow(force = true) {
    if (!this.renderer.shadowMap.enabled) return;
    // Sunlight and sky interpolate every frame; cached shadow maps only need a new
    // sample after about 0.8 degrees of movement. Night has no direct sunlight.
    if (!force && (this.state.sunIntensity < .025 || this.shadowDirection.dot(this.direction) > .9999)) return;
    this.shadowDirection.copy(this.direction);
    this.renderer.shadowMap.needsUpdate = true;
    this.sun.shadow.needsUpdate = true;
  }

  setQuality(level) {
    this.quality = ['high', 'medium', 'low'].includes(level) ? level : 'medium';
    const size = { high: 2048, medium: 1024, low: 512 }[this.quality];
    if (this.sun.shadow.mapSize.x !== size) {
      this.sun.shadow.mapSize.set(size, size);
      this.sun.shadow.map?.dispose();
      this.sun.shadow.map = null;
    }
    this.apply();
    this.invalidateShadow();
  }

  updateShadowFocus(camera, target) {
    this.target.copy(target);
    const span = THREE.MathUtils.clamp(camera.position.distanceTo(target) * .62, 95, 1500);
    const shadowCamera = this.sun.shadow.camera;
    Object.assign(shadowCamera, { left: -span, right: span, top: span, bottom: -span, near: 10, far: 4200 });
    shadowCamera.updateProjectionMatrix();
    this.sun.shadow.bias = -.000015;
    this.sun.shadow.normalBias = THREE.MathUtils.clamp(span / this.sun.shadow.mapSize.x * .35, .025, .35);
    this.sun.target.position.copy(target);
    this.sun.position.copy(target).addScaledVector(this.direction, 1900);
    this.invalidateShadow();
    this.requestRender();
  }

  dispose() {
    for (const root of [...this.models.keys()]) this.unregisterModel(root);
    this.sky.removeFromParent();
    this.sky.geometry.dispose();
    this.sky.material.dispose();
  }
}

const WINDOW_COLOR = new THREE.Color('#edcc96');
const LAMP_COLOR = new THREE.Color('#ffe3ac');
