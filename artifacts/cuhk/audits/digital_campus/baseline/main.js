import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { searchBuildings } from './search.js';
import './style.css';

const $ = selector => document.querySelector(selector);
const mobile = () => innerWidth <= 600;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#dce7df');
scene.fog = new THREE.Fog('#dce7df', 3100, 7600);
const camera = new THREE.PerspectiveCamera(43, innerWidth / innerHeight, 3, 15000);
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
} catch (error) {
  $('#loading h2').textContent = '当前浏览器无法显示三维校园';
  $('#loading-detail').textContent = '请启用浏览器硬件加速，或使用支持 WebGL 2 的 Chrome / Edge。';
  $('#retry-button').hidden = false;
  $('#retry-button').addEventListener('click', () => location.reload());
  $('#scene-status').textContent = '三维显示不可用';
  throw error;
}
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.7));
renderer.setSize(innerWidth, innerHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFShadowMap;
$('#viewport').append(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = .09;
controls.minDistance = 65;
controls.maxDistance = 4700;
controls.maxPolarAngle = Math.PI * .465;
controls.minPolarAngle = .015;
controls.screenSpacePanning = false;
controls.zoomSpeed = .7;
controls.rotateSpeed = .65;
const fill = new THREE.HemisphereLight('#e8f0ff', '#8a9271', 1.35);
scene.add(fill);
const sun = new THREE.DirectionalLight('#fff1d6', 2.8);
sun.position.set(-700, 1250, 850);
sun.target.position.set(0, 30, 0);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
Object.assign(sun.shadow.camera, { left: -1550, right: 1550, top: 1550, bottom: -1550, near: 10, far: 3700 });
sun.shadow.bias = -.00002;
sun.shadow.normalBias = .55;
scene.add(sun, sun.target);
const pmrem = new THREE.PMREMGenerator(renderer);
const room = new RoomEnvironment();
const environment = pmrem.fromScene(room, .04);
scene.environment = environment.texture;
scene.environmentIntensity = .3;
room.dispose();
pmrem.dispose();

const presets = {
  overview: { position: [1370, 1140, 1460], target: [0, 60, -65] },
  central: { position: [365, 435, 565], target: [-110, 95, 0] },
  hill: { position: [525, 615, 455], target: [-120, 140, -245] },
  coast: { position: [1370, 720, -1170], target: [50, 80, -80] },
};
let transition = null;
let selected = null;
let buildings = [];
const buildingsById = new Map();
const buildingMeshes = new Map();
const pickables = [];
let labelsEnabled = true;
let loaded = false;
let evening = false;
let labelItems = [];
let lastLabelsTime = 0;
let lastFrameTime = 0;
let dirty = true;
let toastTimer;
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const projected = new THREE.Vector3();
const landmarkIds = ['134410449', '107139030', '134408696', '135156315', '135312912'];
const highlightMaterials = new Map();

function updateShadowFocus() {
  // Concentrate the same shadow map on the viewed buildings when zoomed in.
  const span = THREE.MathUtils.clamp(camera.position.distanceTo(controls.target) * .7, 140, 1550);
  const shadow = sun.shadow.camera;
  shadow.left = shadow.bottom = -span;
  shadow.right = shadow.top = span;
  shadow.updateProjectionMatrix();
  sun.target.position.copy(controls.target);
  sun.position.copy(controls.target).add(new THREE.Vector3(evening ? -1300 : -700, evening ? 680 : 1250, 850));
  sun.shadow.normalBias = Math.max(.035, span / 1550 * .4);
  renderer.shadowMap.needsUpdate = true;
  dirty = true;
}

function toast(message) {
  $('#toast').textContent = message;
  $('#toast').classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 2800);
}

function flyTo(position, target, duration = 1300) {
  if (reducedMotion) duration = 0;
  transition = { start: performance.now(), duration, from: camera.position.clone(), to: new THREE.Vector3(...position), fromTarget: controls.target.clone(), toTarget: new THREE.Vector3(...target) };
}

function setView(name, immediate = false) {
  const preset = presets[name];
  clearSelection();
  const position = [...preset.position];
  // Portrait screens need a wider view to keep the campus in the frame.
  if (mobile()) {
    for (let i = 0; i < 3; i++) position[i] = preset.target[i] + (position[i] - preset.target[i]) * 1.25;
  }
  flyTo(position, preset.target, immediate ? 0 : 1500);
  document.querySelectorAll('.view-button').forEach(button => button.classList.toggle('active', button.dataset.view === name));
}

function clearSelection() {
  if (selected) for (const mesh of buildingMeshes.get(selected.id) ?? []) {
    const original = highlightMaterials.get(mesh);
    if (original) {
      for (const material of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) material.dispose();
      mesh.material = original;
      highlightMaterials.delete(mesh);
    }
  }
  selected = null;
  $('#selection').hidden = true;
  lastLabelsTime = 0;
  dirty = true;
}

function selectBuilding(building, move = true) {
  clearSelection();
  selected = building;
  $('#selected-name').textContent = building.name_zh || building.name;
  $('#selected-en').textContent = building.name_zh && building.name_zh !== building.name ? building.name : '香港中文大学 · 校园建筑';
  $('#selected-height').textContent = Number.isFinite(building.height_m) ? `${building.height_m.toFixed(1)} m` : '未标注';
  $('#selected-source').textContent = ({ estimated: '用途估算', levels: '楼层推算', height_tag: '地图标注', lidar_photo_estimate: '高程与照片估算' })[building.height_source] || '模型数据';
  $('#selected-source').title = building.height_note || '';
  $('#selection').hidden = false;
  for (const mesh of buildingMeshes.get(building.id) ?? []) {
    highlightMaterials.set(mesh, mesh.material);
    const highlight = material => {
      const copy = material.clone();
      if (copy.emissive) { copy.emissive.set('#669051'); copy.emissiveIntensity = .08; }
      return copy;
    };
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(highlight) : highlight(mesh.material);
  }
  if (move) focusBuilding(building, false);
  lastLabelsTime = 0;
  dirty = true;
}

function focusBuilding(building, close = true) {
  const target = new THREE.Vector3(...building.position);
  const size = Math.max(...(building.size || [70, 30, 70]));
  const distance = Math.max(close ? 240 : 460, size * (close ? 3 : 4));
  const direction = camera.position.clone().sub(controls.target).normalize();
  direction.y = Math.max(.52, direction.y);
  direction.normalize();
  const position = target.clone().addScaledVector(direction, distance * (mobile() ? 1.25 : 1));
  flyTo(position.toArray(), target.toArray());
  document.querySelectorAll('.view-button').forEach(button => button.classList.remove('active'));
}

function renderSearch() {
  const query = $('#search').value.trim();
  const results = $('#search-results');
  results.replaceChildren();
  results.hidden = !query;
  $('#discover').hidden = !!query;
  if (!query) return;
  const matches = searchBuildings(buildings, query);
  if (!matches.length) {
    const message = document.createElement('p');
    message.className = 'empty-results';
    message.textContent = loaded ? '没有找到这栋建筑。试试中文简称或英文名称。' : '建筑目录正在载入…';
    results.append(message);
  }
  for (const building of matches) {
    const button = document.createElement('button');
    button.className = 'search-result';
    const name = document.createElement('b');
    name.textContent = building.name_zh || building.name;
    const english = document.createElement('small');
    english.textContent = building.name;
    button.append(name, english);
    button.addEventListener('click', () => {
      selectBuilding(building);
      $('#search').blur();
      if (mobile()) { $('#search').value = ''; renderSearch(); }
    });
    results.append(button);
  }
}

function createLabels() {
  const labelRoot = $('#labels');
  labelItems = buildings.filter(b => b.campus !== false && (b.name_zh || b.name) && !/^building\s|无名称|無名稱/i.test(b.name_zh || b.name)).map(building => {
    const element = document.createElement('button');
    element.className = 'map-label';
    element.textContent = building.name_zh || building.name;
    element.addEventListener('click', () => selectBuilding(building));
    labelRoot.append(element);
    return { building, element, priority: landmarkIds.includes(building.id) ? 0 : 1 };
  });
}

function updateLabels(time) {
  if (time - lastLabelsTime < 90) return;
  lastLabelsTime = time;
  const occupied = [];
  const candidates = [];
  const visible = new Set();
  for (const item of labelItems) {
    if (!labelsEnabled && item.building !== selected) continue;
    projected.set(...item.building.position);
    projected.y += (item.building.size?.[1] ?? 0) / 2 + 8;
    const distance = camera.position.distanceTo(projected);
    projected.project(camera);
    if (projected.z < -1 || projected.z > 1) continue;
    const x = (projected.x * .5 + .5) * innerWidth;
    const y = (-projected.y * .5 + .5) * innerHeight;
    const width = Math.min(250, (item.element.textContent.length * (mobile() ? 9 : 10)) + 22);
    if (x < width / 2 + 12 || x > innerWidth - width / 2 - 65 || y < (mobile() ? 150 : 105) || y > innerHeight - 120) continue;
    if (!mobile() && x < (innerWidth > 1650 ? 360 : innerWidth > 900 ? 333 : 275) && y < 650) continue;
    if (distance > 2700 && item.priority !== 0 && item.building !== selected) continue;
    candidates.push({ ...item, x, y, width, distance });
  }
  candidates.sort((a, b) => Number(b.building === selected) - Number(a.building === selected) || a.priority - b.priority || a.distance - b.distance);
  let count = 0;
  for (const item of candidates) {
    const rect = { left: item.x - item.width / 2 - 8, right: item.x + item.width / 2 + 8, top: item.y - 28, bottom: item.y + 12 };
    if (occupied.some(box => rect.left < box.right && rect.right > box.left && rect.top < box.bottom && rect.bottom > box.top)) continue;
    visible.add(item.element);
    item.element.style.transform = `translate(${item.x}px,${item.y}px) translate(-50%,-100%)`;
    item.element.classList.toggle('selected', item.building === selected);
    occupied.push(rect);
    if (++count >= (mobile() ? 6 : 15)) break;
  }
  for (const { element } of labelItems) {
    const display = visible.has(element) ? 'block' : 'none';
    if (element.style.display !== display) element.style.display = display;
  }
}

function resize() {
  camera.aspect = innerWidth / innerHeight;
  camera.setViewOffset(innerWidth, innerHeight, mobile() ? 0 : -130, 0, innerWidth, innerHeight);
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
  lastLabelsTime = 0;
  dirty = true;
}
addEventListener('resize', resize);
resize();
setView('overview', true);

controls.addEventListener('start', () => { transition = null; });
controls.addEventListener('change', () => { dirty = true; });
controls.addEventListener('end', updateShadowFocus);
let down;
renderer.domElement.addEventListener('pointerdown', event => { down = { x: event.clientX, y: event.clientY, time: performance.now(), button: event.button }; });
renderer.domElement.addEventListener('pointerup', event => {
  if (!loaded || !down || down.button !== 0 || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 6 || performance.now() - down.time > 500) return;
  pointer.set(event.clientX / innerWidth * 2 - 1, -event.clientY / innerHeight * 2 + 1);
  raycaster.setFromCamera(pointer, camera);
  const hit = raycaster.intersectObjects(pickables, false)[0];
  if (hit) selectBuilding(buildingsById.get(hit.object.userData.buildingId), false);
  else clearSelection();
});

$('#search').addEventListener('input', renderSearch);
$('#search').addEventListener('keydown', event => { if (event.key === 'Enter') $('#search-results button')?.click(); });
document.querySelectorAll('.view-button').forEach(button => button.addEventListener('click', () => setView(button.dataset.view)));
$('#brand-home').addEventListener('click', event => { event.preventDefault(); setView('overview'); });
$('#close-selection').addEventListener('click', clearSelection);
$('#focus-selection').addEventListener('click', () => selected && focusBuilding(selected));
$('#labels-button').addEventListener('click', () => {
  labelsEnabled = !labelsEnabled;
  $('#labels-button').classList.toggle('active', labelsEnabled);
  $('#labels-button').setAttribute('aria-pressed', String(labelsEnabled));
  lastLabelsTime = 0;
});
$('#light-button').addEventListener('click', () => {
  evening = !evening;
  $('#light-button').classList.toggle('active', evening);
  $('#light-button').setAttribute('aria-pressed', String(evening));
  sun.color.set(evening ? '#ffbf80' : '#fff1d6');
  sun.intensity = evening ? 3.2 : 2.8;
  fill.intensity = evening ? 1.0 : 1.35;
  scene.background.set(evening ? '#e4ddce' : '#dce7df');
  scene.fog.color.copy(scene.background);
  updateShadowFocus();
  toast(evening ? '傍晚 · 山坡上的暖光' : '日间 · 清朗的校园');
});
$('#north-button').addEventListener('click', () => {
  const target = controls.target.clone();
  const distance = camera.position.distanceTo(target);
  flyTo([target.x, target.y + distance, target.z + 1], target.toArray());
  document.querySelectorAll('.view-button').forEach(button => button.classList.remove('active'));
});
function zoom(factor) {
  const distance = THREE.MathUtils.clamp(camera.position.distanceTo(controls.target) * factor, controls.minDistance, controls.maxDistance);
  const position = camera.position.clone().sub(controls.target).normalize().multiplyScalar(distance).add(controls.target);
  flyTo(position.toArray(), controls.target.toArray(), 350);
}
$('#zoom-in').addEventListener('click', () => zoom(.72));
$('#zoom-out').addEventListener('click', () => zoom(1.4));
$('#fullscreen-button').addEventListener('click', async () => {
  try { if (document.fullscreenElement) await document.exitFullscreen(); else await document.documentElement.requestFullscreen(); }
  catch { toast('当前窗口不支持全屏，可以放大浏览器窗口。'); }
});
$('#capture-button').addEventListener('click', () => {
  renderer.render(scene, camera);
  renderer.domElement.toBlob(blob => {
    if (!blob) return toast('截图未能保存，请重试。');
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.download = `CUHK-campus-${new Date().toISOString().slice(0, 10)}.png`;
    link.href = url;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    toast('校园视角已保存为 PNG');
  }, 'image/png');
});
for (const selector of ['#about-button', '#source-button']) $(selector).addEventListener('click', () => $('#about-dialog').showModal());
$('#close-about').addEventListener('click', () => $('#about-dialog').close());
$('#about-dialog').addEventListener('click', event => {
  const rect = event.target.getBoundingClientRect();
  if (event.target === $('#about-dialog') && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) $('#about-dialog').close();
});
addEventListener('keydown', event => {
  if (event.key === '/' && document.activeElement.tagName !== 'INPUT' && !$('#about-dialog').open) { event.preventDefault(); $('#search').focus(); }
  if (event.key === 'Escape') { clearSelection(); $('#search').value = ''; renderSearch(); $('#search').blur(); }
});
$('#retry-button').addEventListener('click', () => location.reload());
renderer.domElement.addEventListener('webglcontextlost', event => { event.preventDefault(); toast('图形显示暂时中断，正在恢复…'); });
renderer.domElement.addEventListener('webglcontextrestored', () => location.reload());

const decoder = new DRACOLoader();
decoder.setDecoderPath('/draco/');
decoder.setWorkerLimit(2);
const loader = new GLTFLoader();
loader.setDRACOLoader(decoder);
function loadAsset(url, label, start, range) {
  $('#loading-detail').textContent = label;
  return loader.loadAsync(url, event => {
    $('#loading-progress').style.width = `${start + range * (event.total ? event.loaded / event.total : .5)}%`;
  });
}

function prepareModel(root, isTerrain) {
  root.traverse(object => {
    if (!object.isMesh) return;
    object.receiveShadow = true;
    object.castShadow = !isTerrain;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    for (const material of materials) {
      material.side = THREE.DoubleSide;
      material.envMapIntensity = .3;
    }
    let node = object;
    let id;
    while (node && !id) {
      id = node.userData.osm_id || node.name.match(/web_building_(\d+)/)?.[1];
      node = node.parent;
    }
    if (id && buildingsById.has(String(id))) {
      id = String(id);
      object.userData.buildingId = id;
      if (!buildingMeshes.has(id)) buildingMeshes.set(id, []);
      buildingMeshes.get(id).push(object);
      pickables.push(object);
    }
  });
  scene.add(root);
  dirty = true;
}

async function init() {
  try {
    const response = await fetch('/model/buildings.json');
    if (!response.ok) throw new Error('建筑目录读取失败');
    buildings = await response.json();
    for (const building of buildings) { building.id = String(building.id); buildingsById.set(building.id, building); }
    $('#building-count').textContent = buildings.filter(b => b.campus !== false).length;
    for (const [index, id] of landmarkIds.entries()) {
      const building = buildingsById.get(id);
      if (!building) continue;
      const button = document.createElement('button');
      button.className = 'landmark';
      const number = document.createElement('span');
      number.className = 'landmark-index'; number.textContent = `0${index + 1}`;
      const text = document.createElement('span'); text.textContent = building.name_zh || building.name;
      const arrow = document.createElement('span'); arrow.className = 'arrow'; arrow.textContent = '↗';
      button.append(number, text, arrow);
      button.addEventListener('click', () => selectBuilding(building));
      $('#landmarks').append(button);
    }
    const terrain = await loadAsset('/model/terrain.glb', '正在载入山地与海岸…', 5, 38);
    prepareModel(terrain.scene, true);
    const campus = await loadAsset('/model/campus.glb', '正在载入建筑、道路与绿化…', 43, 49);
    prepareModel(campus.scene, false);
    createLabels();
    $('#loading-detail').textContent = '整理光影，即将进入校园…';
    $('#loading-progress').style.width = '96%';
    await renderer.compileAsync(scene, camera);
    renderer.render(scene, camera);
    renderer.shadowMap.autoUpdate = false;
    loaded = true;
    dirty = true;
    $('#scene-status').textContent = '三维校园 · 自由探索';
    $('#loading-progress').style.width = '100%';
    $('#capture-button').disabled = false;
    $('#loading').classList.add('finished');
    setTimeout(() => { $('#loading').hidden = true; }, 700);
    decoder.dispose();
    renderSearch();
    // Read-only diagnostics support reproducible preview checks.
    window.campusDiagnostics = () => ({ ready: loaded, buildings: buildings.length, pickableBuildings: buildingMeshes.size, triangles: renderer.info.render.triangles, drawCalls: renderer.info.render.calls, selected: selected?.id ?? null, labels: labelItems.filter(item => item.element.style.display === 'block').length, camera: camera.position.toArray(), target: controls.target.toArray() });
  } catch (error) {
    console.error('Campus loading failed', error);
    $('#loading h2').textContent = '校园模型暂时没有载入';
    $('#loading-detail').textContent = '请确认本地服务正常运行后重试。';
    $('#retry-button').hidden = false;
    $('#scene-status').textContent = '载入未完成';
  }
}

renderer.setAnimationLoop(time => {
  if (document.hidden || (mobile() && time - lastFrameTime < 30)) return;
  lastFrameTime = time;
  if (transition) {
    const t = transition.duration ? Math.min((time - transition.start) / transition.duration, 1) : 1;
    const ease = t * t * (3 - 2 * t);
    camera.position.lerpVectors(transition.from, transition.to, ease);
    controls.target.lerpVectors(transition.fromTarget, transition.toTarget, ease);
    if (t === 1) { transition = null; lastLabelsTime = 0; updateShadowFocus(); }
  }
  controls.update();
  // Keep the static campus idle between interactions instead of drawing millions
  // of unchanged triangles continuously.
  if (!dirty && lastLabelsTime !== 0) return;
  const azimuth = controls.getAzimuthalAngle();
  $('#compass-arrow').style.transform = `rotate(${-azimuth * 180 / Math.PI}deg)`;
  camera.updateMatrixWorld();
  if (loaded) updateLabels(time);
  if (dirty) { renderer.render(scene, camera); dirty = false; }
});
init();
