import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Document, NodeIO, Logger } from '@gltf-transform/core';
import { ALL_EXTENSIONS, EXTMeshoptCompression } from '@gltf-transform/extensions';
import { copyToDocument, dedup, prune, weld, simplify, normals, reorder, quantize, unpartition, getBounds } from '@gltf-transform/functions';
import { MeshoptEncoder, MeshoptDecoder, MeshoptSimplifier } from 'meshoptimizer';
import draco from 'draco3dgltf';

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const AUDIT=path.join(ROOT,'audits/digital_campus');
const STAGE=path.join(AUDIT,'stage');
const WEB=path.resolve(ROOT,'../../cuhk-campus-web/public');
const OUT=path.join(WEB,'campus');
const lowOnly=process.argv.includes('--low-only');
const lodSettings={highMeters:150,mediumMeters:850,hysteresis:1.2,releaseGraceMs:3500,
 qualities:{high:{high:150,medium:850,zones:5},medium:{high:100,medium:600,zones:3},low:{high:0,medium:330,zones:2}}};
await fs.mkdir(OUT,{recursive:true});
await Promise.all([MeshoptEncoder.ready,MeshoptDecoder.ready,MeshoptSimplifier.ready]);
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'draco3d.decoder':await draco.createDecoderModule(),'meshopt.encoder':MeshoptEncoder,'meshopt.decoder':MeshoptDecoder
});
const records=[];
const readStart=performance.now();
const source=await io.read(path.join(WEB,'model/campus.glb'));
const dracoReadMs=performance.now()-readStart;
for(const ext of source.getRoot().listExtensionsUsed()) if(ext.extensionName==='KHR_draco_mesh_compression') ext.dispose();
source.setLogger(new Logger(Logger.Verbosity.WARN));
const buildingNodes=source.getRoot().listNodes().filter(n=>n.getExtras().osm_id);
const metadata=JSON.parse(await fs.readFile(path.join(WEB,'model/buildings.json'),'utf8'));
const byId=new Map(metadata.map(b=>[b.id,b]));
if(buildingNodes.length!==369) throw new Error(`Expected 369 buildings, got ${buildingNodes.length}`);
function subset(nodes) {
  const doc=new Document().setLogger(new Logger(Logger.Verbosity.WARN));
  const mapping=copyToDocument(doc,source,nodes);
  const scene=doc.createScene('Campus');
  nodes.forEach(n=>scene.addChild(mapping.get(n)));
  return doc;
}
function stats(doc) {
  let triangles=0,drawCalls=0,vertices=0;
  for(const m of doc.getRoot().listMeshes()) for(const p of m.listPrimitives()) {
    triangles+=p.getIndices().getCount()/3; drawCalls++; vertices+=p.getAttribute('POSITION').getCount();
  }
  const bounds=getBounds(doc.getRoot().listScenes()[0]);
  return {triangles,drawCalls,vertices,bounds};
}
async function compress(doc,file) {
  await doc.transform(dedup(),prune(),weld(),reorder({encoder:MeshoptEncoder}),
    quantize({pattern:/^(NORMAL|COLOR_)/,quantizeNormal:10,quantizeColor:8}),unpartition());
  // Full float32 positions preserve road clearances and planarity. Normals and
  // colors alone are quantized, avoiding 16-bit whole-campus position rounding.
  doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method:EXTMeshoptCompression.EncoderMethod.FILTER});
  const start=performance.now(); await io.write(path.join(OUT,file),doc);
  const writeMs=performance.now()-start;
  const entry={url:`/campus/${file}`,bytes:(await fs.stat(path.join(OUT,file))).size,...stats(doc),writeMs};
  const decodeStart=performance.now();
  const decoded=await io.read(path.join(OUT,file));
  entry.decodeMs=performance.now()-decodeStart;
  const check=stats(decoded);
  if(check.triangles!==entry.triangles) throw new Error(`Triangle roundtrip mismatch ${file}`);
  if(check.bounds.min.some((v,i)=>Math.abs(v-entry.bounds.min[i])>.001)||check.bounds.max.some((v,i)=>Math.abs(v-entry.bounds.max[i])>.001)) throw new Error(`Bounds roundtrip mismatch ${file}`);
  records.push(entry); console.log('ASSET',JSON.stringify(entry));
  return entry;
}
function vertexColorBuildings(doc) {
  const buffer=doc.getRoot().listBuffers()[0]||doc.createBuffer();
  const material=doc.createMaterial('Campus distance colors').setBaseColorFactor([1,1,1,1]).setRoughnessFactor(.82).setMetallicFactor(0).setDoubleSided(true);
  const glassMaterial=doc.createMaterial('Campus distance glazing').setBaseColorFactor([1,1,1,1]).setRoughnessFactor(.29).setMetallicFactor(.15).setDoubleSided(true);
  for(const mesh of doc.getRoot().listMeshes()) {
    const allParts=mesh.listPrimitives();
    const glazing=p=>/glaz|glass/i.test(p.getMaterial()?.getName()||'');
    for(const parts of [allParts.filter(p=>!glazing(p)),allParts.filter(glazing)]) {
    if(!parts.length)continue;
    let nv=0,ni=0; for(const p of parts){nv+=p.getAttribute('POSITION').getCount();ni+=p.getIndices().getCount();}
    const positions=new Float32Array(nv*3),normals=new Float32Array(nv*3),colors=new Float32Array(nv*3),indices=new Uint32Array(ni);
    let vo=0,ioff=0;
    for(const p of parts){
      const pos=p.getAttribute('POSITION').getArray(),nor=p.getAttribute('NORMAL').getArray(),idx=p.getIndices().getArray();
      const color=p.getMaterial().getBaseColorFactor();
      positions.set(pos,vo*3); normals.set(nor,vo*3);
      for(let i=0;i<pos.length/3;i++)colors.set(color.slice(0,3),(vo+i)*3);
      for(let i=0;i<idx.length;i++)indices[ioff+i]=idx[i]+vo;
      vo+=pos.length/3;ioff+=idx.length;
      mesh.removePrimitive(p);
    }
    const prim=doc.createPrimitive().setMaterial(glazing(parts[0])?glassMaterial:material);
    for(const [name,array,type] of [['POSITION',positions,'VEC3'],['NORMAL',normals,'VEC3'],['COLOR_0',colors,'VEC3']])
      prim.setAttribute(name,doc.createAccessor().setType(type).setArray(array).setBuffer(buffer));
    prim.setIndices(doc.createAccessor().setType('SCALAR').setArray(indices).setBuffer(buffer));mesh.addPrimitive(prim);
    }
  }
}
const initial=[];
if(!lowOnly){
 const base=subset(source.getRoot().listNodes().filter(n=>n.getMesh()&&!n.getExtras().osm_id&&n.getExtras().category!=='vegetation'));
 initial.push({...await compress(base,'site.glb'),kind:'site'});
}
const low=await io.read(path.join(STAGE,'building-shells.glb'));
low.setLogger(new Logger(Logger.Verbosity.WARN));
// Existing Blender footprints provide the silhouette LOD. Keep the recently
// corrected Shaw and the seven authored landmarks in their existing geometry.
const lowIds=new Set(low.getRoot().listNodes().map(n=>String(n.getExtras().osm_id)));
const shawLow=low.getRoot().listNodes().find(n=>String(n.getExtras().osm_id)==='107139044');
shawLow?.dispose();
const supplements=buildingNodes.filter(n=>!lowIds.has(String(n.getExtras().osm_id))||String(n.getExtras().osm_id)==='107139044');
const added=copyToDocument(low,source,supplements);
supplements.forEach(n=>low.getRoot().listScenes()[0].addChild(added.get(n)));
const completeIds=new Set(supplements.map(n=>String(n.getExtras().osm_id)));
const lowNodes=new Map(low.getRoot().listNodes().map(n=>[String(n.getExtras().osm_id),n]));
let facadeTriangles=0, facadeBuildings=0;
for(const node of buildingNodes){
 const id=String(node.getExtras().osm_id);
 if(completeIds.has(id))continue;
 const facade=node.getMesh().listPrimitives().filter(p=>/glaz|glass|_Accent_|TerracottaTile/i.test(p.getMaterial()?.getName()||''));
 if(!facade.length)continue;
 const mapped=copyToDocument(low,source,facade);
 for(const primitive of facade){lowNodes.get(id).getMesh().addPrimitive(mapped.get(primitive));facadeTriangles+=primitive.getIndices().getCount()/3;}
 facadeBuildings++;
}
vertexColorBuildings(low);
initial.push({...await compress(low,'buildings-low.glb'),kind:'buildings-low'});
if(lowOnly){
 const manifest=JSON.parse(await fs.readFile(path.join(OUT,'manifest.json'),'utf8'));
 manifest.lod=lodSettings;
 manifest.initial=manifest.initial.map(entry=>entry.kind==='buildings-low'?initial[0]:entry);
 const report=JSON.parse(await fs.readFile(path.join(AUDIT,'digital_asset_report.json'),'utf8'));
 report.initialBytes=manifest.initial.reduce((s,a)=>s+a.bytes,0);
 report.initialTriangles=manifest.initial.reduce((s,a)=>s+a.triangles,0);
 report.initialDrawCalls=manifest.initial.reduce((s,a)=>s+a.drawCalls,0);
 report.assets=report.assets.map(entry=>entry.url==='/campus/buildings-low.glb'?records[0]:entry);
 report.lowFacadePreservation={facadeBuildings,facadeTriangles,glazingSeparateForNightLighting:true,noInventedWindowGeometry:true};
 await fs.writeFile(path.join(OUT,'manifest.json'),JSON.stringify(manifest,null,2));
 await fs.writeFile(path.join(AUDIT,'digital_asset_report.json'),JSON.stringify(report,null,2));
 console.log('LOW_UPDATE',JSON.stringify({initialBytes:report.initialBytes,initialTriangles:report.initialTriangles,initialDrawCalls:report.initialDrawCalls,...report.lowFacadePreservation}));
 process.exit(0);
}
const zones=new Map();
for(const node of buildingNodes){
 const id=String(node.getExtras().osm_id), b=byId.get(id);
 const col=Math.max(0,Math.min(3,Math.floor((b.position[0]+1200)/600)));
 const row=Math.max(0,Math.min(3,Math.floor((b.position[2]+1200)/600)));
 const key=`zone_${row}_${col}`;
 if(!zones.has(key))zones.set(key,{id:key,nodes:[],buildings:[],center:[col*600-900,100,row*600-900]});
 zones.get(key).nodes.push(node);zones.get(key).buildings.push(id);
}
const zoneEntries=[];
for(const zone of zones.values()){
 const high=await compress(subset(zone.nodes),`${zone.id}-high.glb`);
 const mediumDoc=subset(zone.nodes);
 for(const mesh of mediumDoc.getRoot().listMeshes())for(const primitive of mesh.listPrimitives())primitive.setAttribute('NORMAL',null);
 await mediumDoc.transform(weld(),simplify({simplifier:MeshoptSimplifier,ratio:.35,error:.003}),normals({overwrite:true}));
 const medium=await compress(mediumDoc,`${zone.id}-medium.glb`);
 zoneEntries.push({id:zone.id,buildings:zone.buildings,center:zone.center,bounds:high.bounds,levels:{medium,high}});
}
const terrainReport=JSON.parse(await fs.readFile(path.join(STAGE,'terrain_report.json'),'utf8'));
for(const tile of terrainReport.tiles){
 const doc=await io.read(path.join(STAGE,tile.file));doc.setLogger(new Logger(Logger.Verbosity.WARN));
 initial.unshift({...await compress(doc,tile.file),kind:'terrain'});
}
// Compare codecs on identical complete building/site topology, not reduced LOD.
const comparison=await compress(subset(source.getRoot().listNodes().filter(n=>n.getMesh())),'codec-comparison.glb');
await fs.rename(path.join(OUT,'codec-comparison.glb'),path.join(AUDIT,'codec-comparison-meshopt.glb'));
const previous=JSON.parse(await fs.readFile(path.join(WEB,'model/validation.json'),'utf8'));
const manifest={version:1,coordinateSystem:'Three.js metres: east, HKPD elevation, south',
 ground:'/campus/heightfield.json',buildings:'/model/buildings.json',initial,zones:zoneEntries,
 lod:lodSettings,
 integrity:{source:terrainReport.source,sourceUnchanged:true,buildingCount:369,
  originalRoadsSportsPreserved:true,vegetationExcluded:true,trackPlanes:previous.track_planes,
  shawScience:previous.shaw_science},
 compression:'EXT_meshopt_compression; float32 positions, quantized normals/colors'};
await fs.writeFile(path.join(OUT,'manifest.json'),JSON.stringify(manifest,null,2));
const report={initialBytes:initial.reduce((s,a)=>s+a.bytes,0),initialTriangles:initial.reduce((s,a)=>s+a.triangles,0),
 initialDrawCalls:initial.reduce((s,a)=>s+a.drawCalls,0),zoneCount:zoneEntries.length,allRoundTripsPassed:true,
 codecComparison:{dracoBytes:(await fs.stat(path.join(WEB,'model/campus.glb'))).size,dracoReadMs,
  meshoptBytes:comparison.bytes,meshoptReadMs:comparison.decodeMs,note:'Node single-run whole-file decode comparison; not a browser FPS benchmark. Same topology including static trees. Production uses streamed subsets with restored tree instances.'},
 terrain:terrainReport,assets:records};
await fs.writeFile(path.join(AUDIT,'digital_asset_report.json'),JSON.stringify(report,null,2));
console.log('COMPLETE',JSON.stringify({...report,assets:undefined,terrain:undefined}));
