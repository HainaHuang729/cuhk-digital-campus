import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ecologyPlaces } from './src/ui/EcologyUI.js';
import { matchesEcologyFilter } from './src/ui/BuildingLabels.js';
import { Box3, PerspectiveCamera, Ray, Vector3 } from 'three';
import { CameraFlight } from './src/core/CameraFlight.js';

test('ecology sample has sourced area markers, usable coordinates and working filters',()=>{
  const data=JSON.parse(readFileSync(new URL('./public/campus/ecology.json',import.meta.url)));
  assert.ok(data.plants.length>=5&&data.plants.length<=12);
  assert.ok(data.points.length>=3&&data.points.length<=8);
  const places=ecologyPlaces(data);
  assert.equal(new Set(places.map(p=>p.id)).size,places.length);
  for(const p of places){
    assert.ok(p.name_zh&&p.description&&p.verifiedAt);
    assert.ok(['exact','approximate','inferred'].includes(p.confidence));
    assert.ok(p.position.length===3&&p.position.every(Number.isFinite));
    assert.ok(Math.abs(p.position[0]-232)<220&&Math.abs(p.position[2]-445)<220,'sample stays around the documented lake area');
    assert.ok(Array.isArray(p.source)&&p.source.length);
    assert.ok(p.source.some(source=>/^https:\/\/(?:[^/]+\.)?cuhk\.edu\.hk\//.test(source.url)),'each location needs a CUHK source');
    for(const source of p.source)assert.match(source.url,/^https:\/\/(?:[^/]+\.)?(?:cuhk\.edu\.hk|gov\.hk)\//);
    if(p.type==='plant'){
      assert.ok(p.scientificName&&p.nameEn&&p.visualType&&p.approximateLocation);
      assert.notEqual(p.confidence,'exact','this sample has no surveyed individual trunks');
    }
    assert.ok(matchesEcologyFilter(p,'all'));
    assert.equal(matchesEcologyFilter(p,'plants'),p.type==='plant');
    assert.equal(matchesEcologyFilter(p,'ecology'),p.type!=='plant');
    assert.equal(matchesEcologyFilter(p,'shrub'),p.category==='shrub');
    assert.equal(matchesEcologyFilter(p,'aquatic_edge'),p.habitat==='aquatic_edge'||p.category==='aquatic_edge');
  }
  assert.ok(data.sample.view.position.every(Number.isFinite)&&data.sample.view.target.every(Number.isFinite));
});

test('lake observation views and plant focus remain close, above terrain and clear of buildings',()=>{
  const read=path=>JSON.parse(readFileSync(new URL(path,import.meta.url)));
  const data=read('./public/campus/ecology.json'),buildings=read('./public/model/buildings.json');
  const camera=new PerspectiveCamera(),controls={target:new Vector3(),addEventListener(){}};
  const flight=new CameraFlight(camera,controls);
  flight.ground=read('./public/campus/heightfield.json');flight.buildings=buildings;
  const views=Object.values(data.sample.presentation.views);
  assert.equal(views.length,2);
  const plants=ecologyPlaces(data).filter(p=>p.type==='plant');
  for(const plant of plants){
    flight.focus(plant,false,true);
    assert.deepEqual(flight.active.to.toArray(),plant.presentation.view.position,'plant selection uses its presentation camera on mobile too');
    assert.deepEqual(flight.active.toTarget.toArray(),plant.presentation.view.target);
    views.push(plant.presentation.view);
  }
  for(const view of views){
    camera.position.fromArray(view.position);
    assert.equal(flight.constrain(),false,'a saved view must not be lifted by terrain/building clearance');
    const target=new Vector3(...view.target),distance=camera.position.distanceTo(target);
    assert.ok(distance>=25&&distance<110,'observation view stays within a readable near/mid distance');
    assert.ok((view.position[1]-view.target[1])/distance>Math.cos(Math.PI*.46),'view respects the orbit polar limit');
    const ray=new Ray(camera.position.clone(),target.clone().sub(camera.position).normalize());
    for(const building of buildings){
      const box=new Box3().setFromCenterAndSize(new Vector3(...building.position),new Vector3(...building.size)).expandByScalar(1);
      const hit=ray.intersectBox(box,new Vector3());
      assert.ok(!hit||hit.distanceTo(camera.position)>=distance,`view should not look through building ${building.id}`);
    }
  }
  assert.ok(new Vector3(...data.sample.view.position).distanceTo(new Vector3(...data.sample.view.target))>300,'full-lake overview remains available');
});
