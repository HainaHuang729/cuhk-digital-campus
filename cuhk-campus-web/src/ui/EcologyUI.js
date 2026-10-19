import { matchesEcologyFilter } from './BuildingLabels.js';

const $=selector=>document.querySelector(selector);
export const confidenceLabels={exact:'精确定位',approximate:'近似区域',inferred:'解释性位置'};

export function ecologyPlaces(data){
  return [...data.plants.map(p=>({...p,type:'plant'})),...data.points].map(p=>({
    ...p,poi:true,ecology:true,name_zh:p.nameZh||p.title,name:p.nameEn||p.subtitle||p.title,
    description:p.description||p.notes,position:p.position||p.approximateLocation.position,
    cameraPosition:p.presentation?.view?.position,cameraTarget:p.presentation?.view?.target,
    size:[45,8,45],stories:[],year:null,
  }));
}

/** A small, optional interpretive layer; spatial markers share the existing label layout. */
export class EcologyUI {
  constructor({ui,labels,onSelect,onFocus,onExit,requestRender}){
    Object.assign(this,{ui,labels,onSelect,onFocus,onExit,requestRender});this.active=false;this.data=null;this.pending=null;
    $('#ecology-markers').addEventListener('change',e=>{labels.ecologyMarkers=e.target.checked;labels.last=0;requestRender();});
    $('#ecology-filter').addEventListener('change',e=>{labels.ecologyFilter=e.target.value;this.renderList();labels.last=0;requestRender();});
    $('#ecology-focus').addEventListener('click',()=>this.focus());
    document.querySelectorAll('[data-ecology-view]').forEach(button=>button.addEventListener('click',()=>this.focus(button.dataset.ecologyView)));
    $('#exit-ecology').addEventListener('click',()=>this.setActive(false));
    $('#ecology-retry').addEventListener('click',()=>this.open());
  }
  async load(){
    if(this.data)return this.data;
    if(this.pending)return this.pending;
    this.pending=(async()=>{
      const response=await fetch('/campus/ecology.json');if(!response.ok)throw new Error('生态样板资料暂未载入。');
      const data=await response.json();this.places=ecologyPlaces(data);this.labels.addItems(this.places);this.data=data;
      $('#ecology-summary').textContent=`未圆湖与湖岸 · ${data.plants.length} 种植物 / ${data.points.length} 个生态解说点。仅为有资料依据的小范围样板。`;
      document.querySelectorAll('[data-ecology-view]').forEach(button=>{button.disabled=!data.sample.presentation?.views?.[button.dataset.ecologyView];});
      this.renderList();return data;
    })().finally(()=>{this.pending=null;});return this.pending;
  }
  async open(){
    const first=!this.active;this.setActive(true);$('#ecology-retry').hidden=true;
    try{await this.load();if(first&&this.active)this.onFocus(this.data.sample.view);}
    catch(error){$('#ecology-summary').textContent=error.message;$('#ecology-retry').hidden=false;}
  }
  setActive(value,closePanel=true){
    this.active=value;this.labels.ecology=value;this.labels.last=0;$('#ecology-badge').hidden=!value;document.body.classList.toggle('ecology-mode',value);
    $('[data-panel="ecology-panel"]').setAttribute('aria-pressed',String(value));
    if(!value){if(closePanel)this.ui.showPanel(null);this.onExit();}this.requestRender();
  }
  focus(id){
    const view=id?this.data?.sample.presentation?.views?.[id]:this.data?.sample.view;
    if(view){this.onFocus(view);this.ui.showPanel(null);$('[data-panel="ecology-panel"]').focus({preventScroll:true});}
  }
  renderList(){
    const list=$('#ecology-list');list.replaceChildren();
    for(const p of (this.places||[]).filter(p=>matchesEcologyFilter(p,this.labels.ecologyFilter))){
      list.append(this.ui.placeButton(p.name_zh,`${p.type==='plant'?'植物':'生态'} · ${confidenceLabels[p.confidence]}${p.scientificName?' · '+p.scientificName:''}`,()=>{this.onSelect(p);this.ui.showPanel(null);}));
    }
    if(!list.childElementCount){const note=document.createElement('p');note.className='muted';note.textContent='本样板暂无这一类的可靠资料，留待补充。';list.append(note);}
  }
}
