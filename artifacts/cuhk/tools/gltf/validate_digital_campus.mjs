import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import draco from 'draco3dgltf';
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../..');
const WEB=path.resolve(ROOT,'../../cuhk-campus-web/public');
const { MeshoptDecoder }=await import(pathToFileURL(path.resolve(WEB,'../node_modules/three/examples/jsm/libs/meshopt_decoder.module.js')));
const manifest=JSON.parse(await fs.readFile(path.join(WEB,'campus/manifest.json'),'utf8'));
await MeshoptDecoder.ready;
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.decoder':MeshoptDecoder,'draco3d.decoder':await draco.createDecoderModule()});
const original=await io.read(path.join(WEB,'model/campus.glb'));
const originalNodes=new Map(original.getRoot().listNodes().map(n=>[n.getName(),n]));
function ids(doc){return doc.getRoot().listNodes().map(n=>String(n.getExtras().osm_id||'')).filter(Boolean).sort();}
function bounds(node){
 const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
 for(const p of node.getMesh().listPrimitives()){
  const v=p.getAttribute('POSITION').getArray();for(let i=0;i<v.length;i++){lo[i%3]=Math.min(lo[i%3],v[i]);hi[i%3]=Math.max(hi[i%3],v[i]);}
 }
 return {min:lo,max:hi};
}
function trianglePositionSignature(node){
 let vertices=0;const sums=[0,0,0],xor=[0,0,0];
 for(const p of node.getMesh().listPrimitives()){
  const a=p.getAttribute('POSITION').getArray();const bits=new Uint32Array(a.buffer,a.byteOffset,a.length);
  for(const index of p.getIndices().getArray())for(let j=0;j<3;j++){const value=bits[index*3+j];sums[j]=(sums[j]+value)>>>0;xor[j]=(xor[j]^value)>>>0;vertices++;}
 }
 return {vertices,sums,xor};
}
const report={files:0,allFilesMeshopt:true,all369BuildingIds:true,highBoundsUnchanged:true,siteTrianglePositionsUnchanged:true,tracks:[],shaw:{},sourceUnchanged:manifest.integrity.sourceUnchanged};
const low=await io.read(path.join(WEB,'campus/buildings-low.glb'));
assert.deepEqual(ids(low),ids(original));
const glassPrimitives=doc=>doc.getRoot().listNodes().filter(n=>n.getExtras().osm_id&&n.getMesh()).flatMap(n=>n.getMesh().listPrimitives().filter(p=>/glaz|glass/i.test(p.getMaterial().getName())));
const asNode=primitives=>({getMesh:()=>({listPrimitives:()=>primitives})});
const lowGlass=glassPrimitives(low),sourceGlass=glassPrimitives(original);
assert(lowGlass.length>100);
assert.deepEqual(trianglePositionSignature(asNode(lowGlass)),trianglePositionSignature(asNode(sourceGlass)));
report.lowGlazing={buildingsWithGlazing:lowGlass.length,triangles:lowGlass.reduce((s,p)=>s+p.getIndices().getCount()/3,0),originalGeometryPreserved:true};
const shaw=low.getRoot().listNodes().find(n=>String(n.getExtras().osm_id)==='107139044');
const shawBounds=bounds(shaw);assert(Math.abs(shawBounds.max[1]-117.6)<.001);
let roofVertices=0;for(const p of shaw.getMesh().listPrimitives()){const a=p.getAttribute('POSITION').getArray();for(let i=1;i<a.length;i+=3)if(Math.abs(a[i]-111.6)<.001)roofVertices++;}
assert(roofVertices>20);report.shaw={lowRoofTop:shawBounds.max[1],mainRoofVertices:roofVertices};
const site=await io.read(path.join(WEB,'campus/site.glb'));
for(const node of site.getRoot().listNodes().filter(n=>n.getMesh()))assert.deepEqual(trianglePositionSignature(node),trianglePositionSignature(originalNodes.get(node.getName())),node.getName());
const sport=site.getRoot().listNodes().find(n=>n.getName()==='web_site_05');
for(const [id,x0,x1,height] of [['955764574',100,330,5.33409977],['955764585',370,600,23.60296249]]){
 const heights=[];
 for(const p of sport.getMesh().listPrimitives().filter(p=>p.getMaterial().getName().includes('Track_red'))){
  const a=p.getAttribute('POSITION').getArray();for(let i=0;i<a.length;i+=3)if(a[i]>x0&&a[i]<x1)heights.push(a[i+1]);
 }
 assert(heights.length>100);const lo=Math.min(...heights),hi=Math.max(...heights);assert(hi-lo<.0003);assert(Math.abs(hi-height)<.0003);
 report.tracks.push({id,vertices:heights.length,heightRange:hi-lo,maxHeightError:Math.abs(hi-height)});
}
for(const zone of manifest.zones)for(const level of ['medium','high']){
 const doc=await io.read(path.join(WEB,zone.levels[level].url));assert.deepEqual(ids(doc),[...zone.buildings].sort());
 if(level==='high')for(const node of doc.getRoot().listNodes().filter(n=>n.getMesh())){
  const b=bounds(node),a=bounds(originalNodes.get(node.getName()));assert.deepEqual(a,b,node.getName());
 }
}
for(const entry of [...manifest.initial,...manifest.zones.flatMap(z=>Object.values(z.levels))]){
 const bytes=await fs.readFile(path.join(WEB,entry.url));assert.equal(bytes.length,entry.bytes);
 const json=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());assert(json.extensionsRequired.includes('EXT_meshopt_compression'));report.files++;
}
const ground=JSON.parse(await fs.readFile(path.join(WEB,manifest.ground),'utf8'));
assert.equal(ground.heights.length,ground.rows*ground.cols);assert(ground.heights.every(Number.isFinite));report.groundSamples=ground.heights.length;
await fs.writeFile(path.join(ROOT,'audits/digital_campus/digital_asset_validation.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));
