import * as THREE from 'three';

// Offline, bounded reference only. No city-wide tileset requests run in the viewer.
export class CalibrationLayer {
  constructor(scene, requestRender) {
    this.scene = scene; this.requestRender = requestRender;
    this.group = new THREE.Group(); this.group.name = 'Government public 3D reference';
    this.group.visible = false; scene.add(this.group);
    this.opacity = .45; this.boundsVisible = true; this.verticalMode = 'hkpd';
    this.data = null; this.pending = null; this.materials = [];
  }
  async load() {
    if (this.data) return this.data;
    if (this.pending) return this.pending;
    this.pending = this.loadSample().catch(error => { this.pending = null; throw error; });
    return this.pending;
  }
  async loadSample() {
    const response = await fetch('/calibration/shaw-reference.json');
    if (!response.ok) throw new Error(`参考样板读取失败 (${response.status})`);
    const data = await response.json();
    for (const key of ['building', 'terrain', 'dsm']) {
      const item = data[key];
      if (!Array.isArray(item?.positions) || item.positions.length % 3 || item.positions.length > 100000 || !item.positions.every(value => Number.isFinite(value) && Math.abs(value) < 10000)) throw new Error('参考坐标无效');
      if (item.indices && (!Array.isArray(item.indices) || item.indices.length % 3 || !item.indices.every(i => Number.isInteger(i) && i >= 0 && i < item.positions.length / 3))) throw new Error('参考网格索引无效');
    }
    if (data.building.heightShift.length !== data.building.positions.length / 3 || !data.building.heightShift.every(Number.isFinite)) throw new Error('参考高程转换无效');
    this.data = data;
    const geometry = item => {
      const result = new THREE.BufferGeometry();
      result.setAttribute('position', new THREE.Float32BufferAttribute(item.positions, 3));
      if (item.indices) result.setIndex(item.indices);
      result.computeBoundingSphere(); return result;
    };
    const material = (color, factor = 1) => {
      const result = new THREE.MeshBasicMaterial({color, transparent:true, opacity:this.opacity * factor, depthWrite:false, side:THREE.DoubleSide, polygonOffset:true, polygonOffsetFactor:-1, polygonOffsetUnits:-1});
      this.materials.push([result, factor]); return result;
    };
    this.building = new THREE.Mesh(geometry(data.building), material(0x3adce9));
    this.building.name = data.metrics.matching.sourceId;
    this.terrain = new THREE.Mesh(geometry(data.terrain), material(0xd9bb73, .55));
    const pointMaterial = new THREE.PointsMaterial({color:0xff9c46, size:2, sizeAttenuation:false, transparent:true, opacity:this.opacity, depthWrite:false});
    this.materials.push([pointMaterial, 1]);
    this.dsm = new THREE.Points(geometry(data.dsm), pointMaterial);
    this.group.add(this.terrain, this.building, this.dsm);
    this.modelBox = new THREE.Box3Helper(new THREE.Box3(new THREE.Vector3(...data.modelBounds.min), new THREE.Vector3(...data.modelBounds.max)), 0xf9d365);
    this.referenceBox = new THREE.Box3Helper(new THREE.Box3(), 0x52e9ff);
    for (const box of [this.modelBox, this.referenceBox]) { box.material.depthTest = false; box.renderOrder = 20; this.group.add(box); }
    this.setVerticalMode(this.verticalMode); this.setBoundsVisible(this.boundsVisible);
    this.requestRender(); return data;
  }
  setVisible(value) { this.group.visible = !!value; this.requestRender(); }
  setOpacity(value) {
    if (!Number.isFinite(value)) return;
    this.opacity = THREE.MathUtils.clamp(value, .05, 1);
    for (const [material, factor] of this.materials) material.opacity = this.opacity * factor;
    this.requestRender();
  }
  setBoundsVisible(value) {
    this.boundsVisible = !!value;
    if (this.modelBox) this.modelBox.visible = this.referenceBox.visible = this.boundsVisible;
    this.requestRender();
  }
  setVerticalMode(mode) {
    if (!['hkpd', 'source'].includes(mode)) return;
    this.verticalMode = mode;
    if (this.building) {
      const position = this.building.geometry.attributes.position;
      const original = this.data.building;
      for (let i = 0; i < position.count; i++) position.setY(i, original.positions[i * 3 + 1] - (mode === 'source' ? original.heightShift[i] : 0));
      position.needsUpdate = true;
      this.building.geometry.computeBoundingBox(); this.building.geometry.computeBoundingSphere();
      this.referenceBox.box.copy(this.building.geometry.boundingBox);
    }
    this.requestRender();
  }
  getStats() { return {calibrationVisible:this.group.visible, calibrationLoaded:!!this.data, calibrationVerticalMode:this.verticalMode}; }
  dispose() {
    this.scene.remove(this.group);
    this.group.traverse(object => { object.geometry?.dispose(); object.material?.dispose(); });
  }
}
