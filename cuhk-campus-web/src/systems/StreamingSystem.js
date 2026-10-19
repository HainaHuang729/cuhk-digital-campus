import { Vector3 } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const QUALITY = {
  high: { high: 150, medium: 850, zones: 5 },
  medium: { high: 100, medium: 600, zones: 3 },
  low: { high: 0, medium: 330, zones: 2 },
};

function release(root) {
  const geometries = new Set(), materials = new Set();
  root.traverse(object => {
    if (object.geometry) geometries.add(object.geometry);
    for (const material of (Array.isArray(object.material) ? object.material : [object.material])) if (material) materials.add(material);
  });
  geometries.forEach(geometry => geometry.dispose());
  materials.forEach(material => material.dispose());
}

/** Stream existing architectural detail over a permanent silhouette campus. */
export class StreamingSystem {
  constructor({ scene, loader, buildings, onAdd = () => {}, onRemove = () => {}, requestRender = () => {} }) {
    this.scene = scene;
    this.loader = loader || new GLTFLoader();
    this.loader.setMeshoptDecoder(MeshoptDecoder);
    this.buildings = new Map(buildings.map(building => [String(building.id), building]));
    this.onAdd = onAdd; this.onRemove = onRemove; this.requestRender = requestRender;
    this.quality = 'high'; this.distanceScale = 1; this.manifest = null; this.roots = [];
    this.lowBuildings = new Map(); this.active = new Map(); this.pending = new Map();
    this.desired = new Map(); this.errors = new Map(); this.disposed = false;
    this.lastUpdate = -Infinity; this.loadedBytes = 0; this.loadingCount = 0;
    this.position = new Vector3();
  }

  async loadInitial() {
    const response = await fetch('/campus/manifest.json');
    if (!response.ok) throw new Error('校园分区目录读取失败');
    this.manifest = await response.json();
    const queue = [...this.manifest.initial];
    const worker = async () => {
      while (queue.length && !this.disposed) {
        const entry = queue.shift();
        const gltf = await this.loader.loadAsync(entry.url);
        if (this.disposed) { release(gltf.scene); return; }
        const root = gltf.scene;
        root.userData.campusLayer = entry.kind;
        if (entry.kind === 'buildings-low') root.traverse(object => {
          const id = object.userData.osm_id || object.name.match(/^web_building_(\d+)/)?.[1];
          if (id) this.lowBuildings.set(String(id), object);
        });
        this.roots.push(root); this.scene.add(root); this.onAdd(root, entry.kind);
        this.loadedBytes += entry.bytes; this.requestRender();
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    if (this.lowBuildings.size !== 369) throw new Error('校园建筑目录不完整');
    return this.manifest;
  }

  setQuality(level) {
    if (!QUALITY[level]) throw new Error(`Unknown quality: ${level}`);
    this.quality = level; this.lastUpdate = -Infinity;
  }

  setDistanceScale(value) {
    this.distanceScale = Math.max(.5, Math.min(1.5, Number(value) || 1));
    this.lastUpdate = -Infinity;
  }

  update(camera, target, selectedId) {
    if (!this.manifest || this.disposed) return;
    const now = performance.now();
    if (now - this.lastUpdate < 450) return;
    this.lastUpdate = now;
    const quality = QUALITY[this.quality];
    const candidates = this.manifest.zones.map(zone => {
      let distance = Infinity;
      for (const id of zone.buildings) {
        const building = this.buildings.get(id);
        if (building) distance = Math.min(distance, camera.position.distanceTo(this.position.fromArray(building.position)) - Math.hypot(building.size[0], building.size[2]) * .25);
      }
      const selected = selectedId && zone.buildings.includes(String(selectedId));
      const active = this.active.get(zone.id);
      // Upgrade at the nominal distance; downgrade only 20% farther away.
      const highDistance = quality.high * this.distanceScale * (active?.level === 'high' ? 1.2 : 1);
      const mediumDistance = quality.medium * this.distanceScale * (active ? 1.2 : 1);
      const level = selected ? (this.quality === 'low' ? 'medium' : 'high') : quality.high > 0 && distance < highDistance ? 'high' : distance < mediumDistance ? 'medium' : null;
      return { zone, distance, selected, level };
    }).filter(item => item.level).sort((a, b) => Number(b.selected) - Number(a.selected) || a.distance - b.distance).slice(0, quality.zones);
    this.desired = new Map(candidates.map(item => [item.zone.id, item.level]));
    for (const [id, active] of this.active) {
      if (!this.desired.has(id)) {
        // Keep a short grace period so orbiting a threshold does not churn files.
        if (now - active.lastWanted > 3500) this.removeZone(id);
      } else active.lastWanted = now;
    }
    for (const item of candidates) {
      if (this.loadingCount >= 2) break;
      if (this.active.get(item.zone.id)?.level === item.level || this.pending.has(item.zone.id)) continue;
      if (now - (this.errors.get(item.zone.id) || -Infinity) < 15000) continue;
      this.loadZone(item.zone, item.level);
    }
  }

  async loadZone(zone, level) {
    this.loadingCount++; this.pending.set(zone.id, level);
    try {
      const entry = zone.levels[level];
      const { scene: root } = await this.loader.loadAsync(entry.url);
      if (this.disposed || this.desired.get(zone.id) !== level) { release(root); return; }
      this.removeZone(zone.id);
      root.userData.campusLayer = `buildings-${level}`;
      this.scene.add(root); this.onAdd(root, `buildings-${level}`);
      for (const id of zone.buildings) { const low = this.lowBuildings.get(id); if (low) low.visible = false; }
      this.active.set(zone.id, { root, level, zone, bytes: entry.bytes, lastWanted: performance.now() });
      this.loadedBytes += entry.bytes; this.errors.delete(zone.id); this.requestRender();
    } catch (error) {
      this.errors.set(zone.id, performance.now());
      console.warn(`Campus detail temporarily unavailable: ${zone.id}`, error);
    } finally {
      this.loadingCount--; this.pending.delete(zone.id);
    }
  }

  removeZone(id) {
    const active = this.active.get(id);
    if (!active) return;
    for (const buildingId of active.zone.buildings) { const low = this.lowBuildings.get(buildingId); if (low) low.visible = true; }
    this.onRemove(active.root); this.scene.remove(active.root); release(active.root);
    this.loadedBytes -= active.bytes; this.active.delete(id); this.requestRender();
  }

  get stats() {
    // Compressed payload represented by current scene roots; this is NOT GPU RAM.
    return { zones: this.active.size, pending: this.loadingCount, loadedMiB: this.loadedBytes / 1048576,
      distanceScale: this.distanceScale, lowBuildings: this.lowBuildings.size,
      levels: [...this.active.values()].map(item => `${item.zone.id}:${item.level}`), errors: this.errors.size };
  }

  dispose() {
    this.disposed = true;
    for (const id of [...this.active.keys()]) this.removeZone(id);
    for (const root of this.roots) { this.onRemove(root); this.scene.remove(root); release(root); }
    this.roots.length = 0; this.lowBuildings.clear(); this.loadedBytes = 0;
  }
}
