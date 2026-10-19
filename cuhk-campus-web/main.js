import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { CameraFlight } from './src/core/CameraFlight.js';
import { TimeOfDaySystem } from './src/systems/TimeOfDaySystem.js';
import { PostProcessingSystem } from './src/systems/PostProcessingSystem.js';
import { PerformanceMonitor } from './src/systems/PerformanceMonitor.js';
import { QualitySystem } from './src/systems/QualitySystem.js';
import { StreamingSystem } from './src/systems/StreamingSystem.js';
import { CampusLife } from './src/systems/CampusLife.js';
import { BuildingInteraction } from './src/systems/BuildingInteraction.js';
import { CampusUI } from './src/ui/CampusUI.js';
import { BuildingLabels } from './src/ui/BuildingLabels.js';
import { EcologyUI } from './src/ui/EcologyUI.js';
import { DioramaStyle } from './src/systems/DioramaStyle.js';
import { views, enrichBuildings, enrichAmenities } from './src/data/campusData.js';
import './style.css';

const $=selector=>document.querySelector(selector);
const mobile=()=>innerWidth<=600;
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches;
const scene=new THREE.Scene();
const camera=new THREE.PerspectiveCamera(43,innerWidth/innerHeight,1,15000);
let renderer;
try { renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'}); }
catch(error){$('#loading-detail').textContent='请启用浏览器硬件加速，或使用支持 WebGL 2 的浏览器。';$('#retry-button').hidden=false;$('#retry-button').onclick=()=>location.reload();throw error;}
renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.shadowMap.autoUpdate=false;
renderer.setSize(innerWidth,innerHeight);$('#viewport').append(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement);
Object.assign(controls,{enableDamping:true,dampingFactor:.09,minDistance:25,maxDistance:4700,maxPolarAngle:Math.PI*.46,minPolarAngle:.015,screenSpacePanning:false,zoomSpeed:.7,rotateSpeed:.65,enabled:false});
camera.position.set(1580,1260,1680);controls.target.set(0,60,-65);camera.lookAt(controls.target);
const fill=new THREE.HemisphereLight(),sun=new THREE.DirectionalLight();sun.castShadow=true;scene.add(fill,sun,sun.target);
const pmrem=new THREE.PMREMGenerator(renderer),room=new RoomEnvironment(),environment=pmrem.fromScene(room,.04);
scene.environment=environment.texture;room.dispose();pmrem.dispose();

let dirty=true,loaded=false,entered=false,selected=null,buildings=[],amenities=[],buildingsById=new Map(),interaction,labels,streaming,life,ecology,calibration,calibrationLoading;
let lastFrame=0,mobileDeadline=0,lastUI=0,lastStreaming=0,lastShadow=0,elapsed=0,toastTimer,benchmarkUntil=0;
const requestRender=()=>{dirty=true;};
const diorama=new DioramaStyle();
function toast(text){$('#toast').textContent=text;$('#toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('visible'),3200);}
const timeSystem=new TimeOfDaySystem({scene,renderer,sun,fill,requestRender});timeSystem.setTime(16.5);
timeSystem.setOverrides({exposure:.87,environment:1.15});
const post=new PostProcessingSystem({scene,renderer,camera});
const flight=new CameraFlight(camera,controls,{reducedMotion,onComplete:()=>timeSystem.updateShadowFocus(camera,controls.target)});
const monitor=new PerformanceMonitor(renderer,scene);
const quality=new QualitySystem(renderer,{mobile:mobile(),onChange:level=>{
  timeSystem.setQuality(level);post.setQuality(level);streaming?.setQuality(level);life?.setQuality(level);if(labels)labels.quality=level;resize();
},notify:toast});
timeSystem.setQuality(quality.level);post.setQuality(quality.level);

const ui=new CampusUI({
  onSelect:selectBuilding,onView:setView,onFocus:b=>{flight.focus(b,true,mobile());requestRender();},
  onExplore:b=>{flight.focus(b,false,mobile());ui.showBuilding(null);toast('自由旋转，探索地点周围的空间');},
  onClose:clearSelection,onPanel:id=>{if(labels)labels.last=0;if(id==='ecology-panel')ecology?.open();else if(id&&id!=='time-panel'&&ecology?.active)ecology.setActive(false,false);requestRender();},
  onPhoto:()=>{if(labels){labels.hidden=ui.photo;labels.last=0;}requestRender();},
  onTime:hours=>{timeSystem.setTime(hours);ui.updateTime(timeSystem.state);life?.setNightAmount(timeSystem.state.nightAmount);},
  onPlay:value=>{timeSystem.setPlaying(value);requestRender();},
});ui.updateTime(timeSystem.state);

function clearSelection(){selected=null;interaction?.setSelected(null);ui.showBuilding(null);if(labels){labels.selected=null;labels.last=0;}requestRender();}
function selectBuilding(building,close=false){if(!building||!entered)return;selected=building;interaction.setSelected(building.poi?building.buildingId||null:building.id);ui.showBuilding(building);if(mobile())ui.showPanel(null);labels.selected=building.id;labels.last=0;flight.focus(building,close,mobile());streaming.lastUpdate=-Infinity;requestRender();}
function setView(name){if(ecology?.active)ecology.setActive(false);clearSelection();const view=views[name];const p=view.position.map((value,i)=>view.target[i]+(value-view.target[i])*(mobile()?1.2:1));flight.flyTo(p,view.target,1800);requestRender();}
function resize(){camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);post.setSize(innerWidth,innerHeight);if(labels)labels.last=0;requestRender();}
addEventListener('resize',resize);resize();
controls.addEventListener('change',requestRender);
controls.addEventListener('end',()=>timeSystem.updateShadowFocus(camera,controls.target));
controls.addEventListener('start',()=>{benchmarkUntil=0;interaction?.setHovered(null);});

$('#enter-button').addEventListener('click',()=>{
  if(!loaded||entered)return;entered=true;controls.enabled=true;document.body.classList.remove('at-entry');$('#entry').classList.add('leaving');
  setTimeout(()=>{$('#entry').hidden=true;},reducedMotion?0:1050);
  const target=[0,65,-65];flight.flyTo(mobile()?[1450,1100,1480]:[1120,900,1180],target,2800);if(labels){labels.hidden=false;labels.last=0;}requestRender();
});
$('#brand-home').addEventListener('click',e=>{e.preventDefault();if(entered)setView('overview');});
$('#labels-button').addEventListener('click',()=>{if(!labels)return;labels.enabled=!labels.enabled;labels.last=0;$('#labels-button').setAttribute('aria-pressed',String(labels.enabled));$('#labels-button span').textContent=labels.enabled?'ON':'OFF';requestRender();});
$('#diorama-style').addEventListener('change',event=>{
  clearSelection();diorama.setPreset(event.target.value);
  timeSystem.setOverrides({exposure:diorama.enabled?.87:1,environment:diorama.enabled?1.15:1});
  timeSystem.invalidateShadow(true);requestRender();
});
$('#diorama-view').addEventListener('click',()=>{
  clearSelection();ui.showPanel(null);
  flight.flyTo(mobile()?[480,430,860]:[400,310,740],[228,12,430],1800);requestRender();
});
document.querySelectorAll('[data-amenity-type]').forEach(button=>button.addEventListener('click',()=>{
  if(!labels)return;const type=button.dataset.amenityType;labels.types[type]=!labels.types[type];labels.last=0;
  button.setAttribute('aria-pressed',String(labels.types[type]));requestRender();
}));
$('#north-button').addEventListener('click',()=>{const t=controls.target,d=camera.position.distanceTo(t);flight.flyTo([t.x,t.y+d,t.z+1],t.toArray());requestRender();});
function zoom(factor){const d=THREE.MathUtils.clamp(camera.position.distanceTo(controls.target)*factor,controls.minDistance,controls.maxDistance);const p=camera.position.clone().sub(controls.target).normalize().multiplyScalar(d).add(controls.target);flight.flyTo(p.toArray(),controls.target.toArray(),450);requestRender();}
$('#zoom-in').addEventListener('click',()=>zoom(.74));$('#zoom-out').addEventListener('click',()=>zoom(1.35));
$('#fullscreen-button').addEventListener('click',async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{toast('当前窗口不支持全屏，可以放大浏览器窗口。');}});
$('#capture-button').addEventListener('click',()=>{
  post.render(camera.position.distanceTo(controls.target));renderer.domElement.toBlob(blob=>{
    if(!blob)return toast('画面未能保存，请重试。');const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`CUHK-${$('#scene-time').textContent.replace(':','')}-${new Date().toISOString().slice(0,10)}.png`;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);toast('已保存当前校园画面');
  },'image/png');
});
$('#about-button').addEventListener('click',()=>$('#about-dialog').showModal());$('#close-about').addEventListener('click',()=>$('#about-dialog').close());
$('#about-dialog').addEventListener('click',event=>{if(event.target!==$('#about-dialog'))return;const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)event.target.close();});
$('#retry-button').addEventListener('click',()=>location.reload());

let down,hoverAt=0;
renderer.domElement.addEventListener('pointerdown',event=>{down={x:event.clientX,y:event.clientY,time:performance.now(),button:event.button};});
renderer.domElement.addEventListener('pointerup',event=>{
  if(!entered||!down||down.button!==0||Math.hypot(event.clientX-down.x,event.clientY-down.y)>6||performance.now()-down.time>600)return;
  const id=interaction.pick(event.clientX,event.clientY);if(id)selectBuilding(buildingsById.get(id));else{clearSelection();ui.showPanel(null);}
});
renderer.domElement.addEventListener('dblclick',event=>{if(!entered)return;const id=interaction.pick(event.clientX,event.clientY);if(id)selectBuilding(buildingsById.get(id),true);});
renderer.domElement.addEventListener('pointermove',event=>{
  if(!entered||event.buttons||event.pointerType==='touch'||performance.now()-hoverAt<110)return;hoverAt=performance.now();
  const id=interaction.pick(event.clientX,event.clientY);interaction.setHovered(id);renderer.domElement.style.cursor=id?'pointer':'grab';
});
renderer.domElement.addEventListener('pointerleave',()=>interaction?.setHovered(null));

function benchmark(){if(!entered)return;controls.autoRotate=!controls.autoRotate;controls.autoRotateSpeed=.35;monitor.panel.hidden=false;benchmarkUntil=controls.autoRotate?performance.now()+12000:0;requestRender();}
$('#benchmark-button').addEventListener('click',benchmark);
$('#quality-select').addEventListener('change',event=>{const value=event.target.value;quality.set(value==='auto'?(mobile()?'low':'high'):value,value==='auto');});
for(const [id,name] of [['exposure','exposure'],['fog','fog'],['environment','environment'],['sun','sunAzimuth']])$('#debug-'+id).addEventListener('input',e=>timeSystem.setOverrides({[name]:Number(e.target.value)}));
$('#debug-shadow').addEventListener('change',e=>timeSystem.setOverrides({shadows:e.target.checked}));
$('#debug-ao').addEventListener('change',e=>{post.setEnabled(e.target.checked);requestRender();});
$('#debug-people').addEventListener('change',e=>life?.setPeopleEnabled(e.target.checked));
$('#debug-vegetation').addEventListener('change',e=>life?.setVegetationEnabled(e.target.checked));
$('#debug-lod').addEventListener('input',e=>{streaming?.setDistanceScale?.(Number(e.target.value));requestRender();});
$('#close-debug').addEventListener('click',()=>{$('#debug-panel').hidden=true;});
$('#debug-ecology-visuals').addEventListener('change',e=>{life?.setEcologyVisualsEnabled(e.target.checked);timeSystem.invalidateShadow();requestRender();});
async function loadCalibration(){
  if(calibration?.data)return calibration;
  if(calibrationLoading)return calibrationLoading;
  $('#calibration-status').textContent='正在读取逸夫科学大楼的小范围参考裁片…';
  calibrationLoading=(async()=>{
    const {CalibrationLayer}=await import('./src/systems/CalibrationLayer.js');
    calibration??=new CalibrationLayer(scene,requestRender);await calibration.load();
    calibration.setOpacity(Number($('#calibration-opacity').value));calibration.setBoundsVisible($('#calibration-bounds').checked);
    calibration.setVerticalMode($('#calibration-vertical').value);
    $('#calibration-status').textContent='政府公开三维数据参考层 · 局部建筑与 DTM / DSM。';
    const metrics=$('#calibration-metrics');metrics.replaceChildren();
    // The layer supplies qualified text so unknown measurements never become zeroes.
    for(const text of calibration.data.summary||[]){const p=document.createElement('p');p.textContent=text;metrics.append(p);}
    for(const source of [calibration.data.sources.governmentBuilding,calibration.data.sources.cedd]){const a=document.createElement('a');a.href=source.documentation;a.target='_blank';a.rel='noreferrer';a.className='source-link';a.textContent=`${source.owner} · ${source.acquiredAt} ↗`;metrics.append(a);}
    $('#calibration-capture').disabled=false;return calibration;
  })().catch(error=>{$('#calibration-status').textContent='参考层未能载入，可取消勾选后重试。';$('#calibration-visible').checked=false;console.warn('Calibration sample',error);throw error;}).finally(()=>{calibrationLoading=null;});
  return calibrationLoading;
}
$('#calibration-visible').addEventListener('change',async()=>{try{const layer=await loadCalibration();layer.setVisible($('#calibration-visible').checked);}catch{}});
$('#calibration-opacity').addEventListener('input',e=>calibration?.setOpacity(Number(e.target.value)));
$('#calibration-bounds').addEventListener('change',e=>calibration?.setBoundsVisible(e.target.checked));
$('#calibration-vertical').addEventListener('change',e=>calibration?.setVerticalMode(e.target.value));
$('#calibration-focus').addEventListener('click',async()=>{try{
  const layer=await loadCalibration();if(ecology?.active)ecology.setActive(false);clearSelection();
  const building=buildingsById.get('107139044');if(building){selected=building;streaming.lastUpdate=-Infinity;}
  const view=layer.data.view;flight.flyTo(view.position,view.target);requestRender();
}catch{}});
$('#calibration-capture').addEventListener('click',async()=>{
  if(!calibration?.data||flight.active)return toast('等待镜头停稳后再导出对照图。');
  const button=$('#calibration-capture');button.disabled=true;
  const wasVisible=$('#calibration-visible').checked,wasBounds=$('#calibration-bounds').checked;
  try{
    const source=renderer.domElement,width=source.width,height=source.height,canvas=document.createElement('canvas');
    canvas.width=width*2;canvas.height=height+110;const ctx=canvas.getContext('2d');
    ctx.fillStyle='#172a2d';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.font='18px sans-serif';ctx.fillStyle='#f0f5ef';
    for(let i=0;i<2;i++){
      calibration.setBoundsVisible(i?wasBounds:false);calibration.setVisible(!!i);post.render(camera.position.distanceTo(controls.target));
      ctx.drawImage(source,width*i,70);ctx.fillText(i?'政府公开三维数据参考层 · 局部建筑 / DTM / DSM':'现有 Blender 校园模型 · 未修改',width*i+20,28);
      ctx.font='13px sans-serif';ctx.fillText(`同一镜头 / ${$('#scene-time').textContent} / ${new Date().toISOString().slice(0,10)} · 建筑参考：${$('#calibration-vertical').selectedOptions[0].textContent}`,width*i+20,52);ctx.font='18px sans-serif';
    }
    ctx.font='13px sans-serif';ctx.fillText('仅逸夫科学大楼样板；现有高度曾参考同源 DSM。对照不等于独立测量验证。',20,canvas.height-15);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));if(!blob)throw new Error('截图失败');
    const image=$('#comparison-image');if(image.src.startsWith('blob:'))URL.revokeObjectURL(image.src);
    image.src=URL.createObjectURL(blob);$('#comparison-save').href=image.src;$('#comparison-dialog').showModal();toast('同镜头对照图已生成，可预览和保存');
  }catch{toast('对照图未能保存，请重试。');}
  finally{calibration.setBoundsVisible(wasBounds);calibration.setVisible(wasVisible);button.disabled=false;requestRender();}
});
$('#close-comparison').addEventListener('click',()=>$('#comparison-dialog').close());
addEventListener('keydown',event=>{
  const editing=/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if(event.key==='Escape'){if(ui.photo)ui.setPhoto(false);else{clearSelection();ui.showPanel(null);$('#debug-panel').hidden=true;$('#search').blur();}controls.autoRotate=false;return;}
  if(!entered||editing||$('#about-dialog').open)return;
  if(event.key==='/'){event.preventDefault();ui.showPanel('places-panel');$('#search').focus();}
  if(event.key.toLowerCase()==='c')ui.setPhoto(!ui.photo);
  if(event.key.toLowerCase()==='d')$('#debug-panel').hidden=!$('#debug-panel').hidden;
  if(event.key.toLowerCase()==='b')benchmark();
});
renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();toast('图形显示暂时中断，正在恢复…');});
renderer.domElement.addEventListener('webglcontextrestored',()=>location.reload());

const decoder=new DRACOLoader().setDecoderPath('/draco/').setWorkerLimit(mobile()?1:2);
const loader=new GLTFLoader().setDRACOLoader(decoder);
function prepareModel(root,kind){
  root.traverse(o=>{if(!o.isMesh)return;o.receiveShadow=true;o.castShadow=!kind.startsWith('terrain');for(const m of Array.isArray(o.material)?o.material:[o.material])m.side=THREE.DoubleSide;});
  timeSystem.registerModel(root);life?.registerLakeModel(root);diorama.register(root);interaction.register(root);requestRender();
}
function removeModel(root){interaction.unregister(root);diorama.unregister(root);life?.unregisterLakeModel(root);timeSystem.unregisterModel(root);requestRender();}
async function init(){
  try{
    const [response,placesResponse]=await Promise.all([fetch('/model/buildings.json'),fetch('/campus/amenities.json')]);
    if(!response.ok||!placesResponse.ok)throw new Error('校园地点目录读取失败');
    buildings=enrichBuildings(await response.json());amenities=enrichAmenities((await placesResponse.json()).items);buildingsById=new Map(buildings.map(b=>[b.id,b]));ui.setData(buildings,amenities);flight.buildings=buildings;
    interaction=new BuildingInteraction({camera,buildings,timeSystem,requestRender});labels=new BuildingLabels(buildings,selectBuilding,amenities);labels.hidden=true;labels.quality=quality.level;
    ecology=new EcologyUI({ui,labels,onSelect:selectBuilding,onFocus:view=>{clearSelection();flight.flyTo(view.position,view.target,1800);requestRender();},onExit:()=>{if(selected?.ecology)clearSelection();},requestRender});
    streaming=new StreamingSystem({scene,loader,buildings,onAdd:prepareModel,onRemove:removeModel,requestRender});streaming.setQuality(quality.level);
    $('#loading-progress').style.width='18%';$('#loading-detail').textContent='载入山地、道路和校园轮廓…';
    const manifest=await streaming.loadInitial();
    $('#loading-progress').style.width='70%';$('#loading-detail').textContent='树影、人行道与校园生活…';
    const groundResponse=await fetch(manifest.ground);if(!groundResponse.ok)throw new Error('地形高度读取失败');flight.ground=await groundResponse.json();
    life=new CampusLife({scene,loader,requestRender});await life.load();life.setQuality(quality.level);life.setNightAmount(timeSystem.state.nightAmount);timeSystem.registerModel(life.group);
    diorama.register(life.group);
    for(const root of streaming.roots){diorama.unregister(root);life.registerLakeModel(root);diorama.register(root);}
    if(reducedMotion)life.setPeopleEnabled(false);
    timeSystem.updateShadowFocus(camera,controls.target);$('#loading-progress').style.width='92%';
    await renderer.compileAsync(scene,camera);post.render(Infinity);loaded=true;requestRender();
    $('#loading-progress').style.width='100%';$('#loading-detail').textContent='校园已就绪';$('#enter-button').disabled=false;$('#capture-button').disabled=false;
    monitor.extra=()=>({quality:quality.level,automatic:quality.automatic,ao:post.active,time:timeSystem.state.hours,night:timeSystem.state.nightAmount,streaming:streaming.stats,life:life.getStats(),ecology:{active:ecology.active,points:ecology.places?.length||0},calibration:calibration?.getStats?.()||{loaded:!!calibration?.data},camera:camera.position.toArray(),target:controls.target.toArray()});
    // Keep the shared decoder alive: streamed assets may still need it.
  }catch(error){console.error('Campus loading failed',error);$('#loading-detail').textContent='校园没有完整载入，请重试。';$('#retry-button').hidden=false;}
}

renderer.setAnimationLoop(now=>{
  if(document.hidden)return;
  if(mobile()){
    if(now<mobileDeadline)return;
    const interval=1000/30;
    // Keep fractional frame time; resetting to now drifts to 26.7 FPS on 160 Hz displays.
    mobileDeadline=now+interval-((now-mobileDeadline)%interval);
  }
  const delta=lastFrame?Math.min((now-lastFrame)/1000,.1):0;lastFrame=now;elapsed+=delta;
  if(benchmarkUntil&&now>benchmarkUntil){controls.autoRotate=false;benchmarkUntil=0;}
  const moving=flight.update(now);controls.update();if(flight.constrain())requestRender();
  const changingTime=timeSystem.update(delta);
  if(loaded){
    if(life.nightAmount!==timeSystem.state.nightAmount)life.setNightAmount(timeSystem.state.nightAmount);
    const living=life.update(elapsed,delta,camera,!reducedMotion);if(living)dirty=true;
    if(entered&&now-lastStreaming>450){streaming.update(camera,controls.target,selected?.poi?selected.buildingId:selected?.id);lastStreaming=now;}
    if(entered&&camera.position.distanceTo(controls.target)<350&&now-lastShadow>220&&timeSystem.state.sunIntensity>.1&&!reducedMotion){timeSystem.invalidateShadow();lastShadow=now;dirty=true;}
    if(now-lastUI>150){ui.updateTime(timeSystem.state);lastUI=now;}
  }
  if(moving||changingTime)dirty=true;
  if(!dirty)return;
  camera.updateMatrixWorld();if(loaded)labels.update(now,camera);
  $('#compass-arrow').style.transform=`rotate(${-controls.getAzimuthalAngle()*180/Math.PI}deg)`;
  post.render(entered?camera.position.distanceTo(controls.target):Infinity);monitor.sample(now);dirty=false;
  const continuous=loaded&&((!reducedMotion&&(life.peopleEnabled||life.vegetationEnabled))||timeSystem.playing||controls.autoRotate);
  if(entered&&!benchmarkUntil)quality.update(monitor.data?.fps,now,!document.hasFocus()||!continuous||streaming.loadingCount>0||!!flight.active);
});
init();
