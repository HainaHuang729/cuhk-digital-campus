import { Vector3 } from 'three';
import { featuredIds } from '../data/campusData.js';

const icons = {
  canteen: '<path d="M4 2v5m3-5v5M2.5 2v4.5A3 3 0 0 0 5.5 9V15M10 2v7h3V2c-2 0-3 2-3 4m3 3v6"/>',
  bus_stop: '<rect x="3" y="2" width="10" height="11" rx="2"/><path d="M3 8h10M5 13v2m6-2v2M6 5h4"/><path d="M5.5 10.5h.01m5 0h.01"/>',
  plant: '<path d="M3 13C2 5 7 2 14 2c0 7-4 12-10 10M3 14l7-7"/>',
  ecology: '<path d="M2 11c2-2 4 2 6 0s4 2 6 0M3 7l4-4 2 3 3-2M8 6v3"/>',
};
const overlaps = (a,b) => a.left<b.right && a.right>b.left && a.top<b.bottom && a.bottom>b.top;

export class BuildingLabels {
  constructor(buildings,onSelect,amenities=[]) {
    this.enabled=false;this.types={canteen:true,bus_stop:true};this.hidden=false;
    this.selected=null;this.last=0;this.point=new Vector3();this.quality='high';this.ecology=false;this.ecologyMarkers=true;this.ecologyFilter='all';
    this.onSelect=onSelect;this.items=[];
    this.addItems([...amenities,...buildings.filter(b=>b.campus!==false&&!/^building\s|无名称|無名稱/i.test(b.name_zh||b.name))]);
  }
  addItems(buildings) {
    const layer=document.querySelector('#labels');
    this.items.push(...buildings.map(b=>{
      const element=document.createElement('button'),name=b.name_zh||b.name;
      element.type='button';element.className=b.poi?'map-label amenity-label':'map-label';
      if(b.ecology)element.classList.add('area-marker');
      element.dataset.kind=b.poi?b.type:'building';element.dataset.pointId=b.id;
      element.setAttribute('aria-label',name);element.title=b.ecology?`${name} · 近似观察区域（非实测点）`:name;
      if(b.poi){
        const icon=document.createElement('span'),text=document.createElement('span');
        icon.className='amenity-icon';icon.setAttribute('aria-hidden','true');
        icon.innerHTML=`<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">${icons[b.type]||icons.ecology}</svg>`;
        text.className='label-name';text.textContent=name;element.append(icon,text);
      }else element.textContent=name;
      element.addEventListener('click',()=>this.onSelect(b));layer.append(element);
      const textWidth=[...name].reduce((width,char)=>width+(/[^\x00-\x7F]/.test(char)?11:6),0);
      return {building:b,element,width:Math.min(246,textWidth+(b.poi?35:18)),priority:b.poi?-1:featuredIds.includes(b.id)?0:1};
    }));this.last=0;
  }
  update(now,camera) {
    if(now-this.last<120)return;this.last=now;
    const mobile=innerWidth<=600,maxNames=this.ecology?5:mobile?6:this.quality==='low'?12:16;
    const panels=[...document.querySelectorAll('.panel:not([hidden]),.amenities-legend,.ecology-badge:not([hidden])')].filter(p=>p.getClientRects().length).map(p=>p.getBoundingClientRect());
    const candidates=[],occupied=[],show=new Set();
    const fits=rect=>rect.left>=14&&rect.right<=innerWidth-65&&rect.top>=85&&rect.bottom<=innerHeight-(mobile?135:90)&&!panels.some(p=>overlaps(rect,p))&&!occupied.some(p=>overlaps(rect,p));
    for(const item of this.items){
      const b=item.building;
      if(this.hidden)continue;
      if(b.ecology){if(!this.ecology||!this.ecologyMarkers||!matchesEcologyFilter(b,this.ecologyFilter))continue;}
      else if(this.ecology||(b.poi?!this.types[b.type]:!this.enabled))continue;
      this.point.set(...b.position);this.point.y+=b.poi?3:b.size[1]/2+5;
      const distance=camera.position.distanceTo(this.point);this.point.project(camera);
      if(this.point.z< -1||this.point.z>1||distance>(b.poi?5000:item.priority&&b.id!==this.selected?2100:Infinity))continue;
      const x=(this.point.x*.5+.5)*innerWidth,y=(-this.point.y*.5+.5)*innerHeight;
      candidates.push({...item,x,y,distance});
    }
    candidates.sort((a,b)=>Number(b.building.id===this.selected)-Number(a.building.id===this.selected)||a.priority-b.priority||a.distance-b.distance);
    // Prefer one name per screen area before filling nearby clusters.
    const cells=new Set();
    for(const item of candidates){const key=`${Math.floor(item.x/(mobile?160:220))}:${Math.floor(item.y/120)}`;item.firstInCell=!cells.has(key);cells.add(key);}
    candidates.sort((a,b)=>Number(b.building.id===this.selected)-Number(a.building.id===this.selected)||a.priority-b.priority||Number(b.firstInCell)-Number(a.firstInCell)||a.distance-b.distance);
    const place=(item,compact)=>{
      const width=compact?25:item.width;
      const rect={left:item.x-width/2-4,right:item.x+width/2+4,top:item.y-31,bottom:item.y+7};
      if(!fits(rect))return false;
      show.add(item.element);occupied.push(rect);
      item.element.style.transform=`translate(${item.x}px,${item.y}px) translate(-50%,-100%)`;
      item.element.style.width=`${width}px`;
      item.element.classList.toggle('compact',compact);item.element.classList.toggle('selected',item.building.id===this.selected);
      return true;
    };
    let names=0;
    for(const item of candidates){if(names>=maxNames)break;if(place(item,false))names++;}
    for(const item of candidates){if(item.building.poi&&!show.has(item.element))place(item,true);}
    for(const item of this.items)item.element.style.display=show.has(item.element)?(item.building.poi?'flex':'block'):'none';
  }
}

export function matchesEcologyFilter(point,filter){return filter==='all'||(filter==='plants'?point.type==='plant':filter==='ecology'?point.type!=='plant':point.category===filter||point.habitat===filter);}
