import { searchBuildings } from '../../search.js';
import { views, featuredIds } from '../data/campusData.js';
import { confidenceLabels } from './EcologyUI.js';
const $ = s => document.querySelector(s);

export class CampusUI {
  constructor({ onSelect, onView, onPhoto, onTime, onPlay, onFocus, onExplore, onClose, onPanel = () => {} }) {
    Object.assign(this,{onSelect,onView,onPhoto,onTime,onPlay,onFocus,onExplore,onClose,onPanel});
    this.buildings=[]; this.amenities=[]; this.category='all'; this.selected=null; this.photo=false; this.playing=false;
    document.querySelectorAll('[data-panel]').forEach(b=>b.addEventListener('click',()=>this.showPanel($( '#'+b.dataset.panel).hidden?b.dataset.panel:null)));
    document.querySelectorAll('.close-panel').forEach(b=>b.addEventListener('click',()=>this.showPanel(null)));
    $('#search').addEventListener('input',()=>this.search());
    $('#search').addEventListener('keydown',e=>{if(e.key==='Enter') $('#places-panel .place-list:not([hidden]) button')?.click();});
    document.querySelectorAll('[data-place-category]').forEach(button=>button.addEventListener('click',()=>{
      this.category=button.dataset.placeCategory;
      document.querySelectorAll('[data-place-category]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
      this.search();
    }));
    $('#close-selection').addEventListener('click',()=>{const ecology=this.selected?.ecology;onClose();if(ecology)$('[data-panel="ecology-panel"]').focus();});
    $('#focus-selection').addEventListener('click',()=>this.selected&&onFocus(this.selected));
    $('#explore-selection').addEventListener('click',()=>this.selected&&onExplore(this.selected));
    $('#story-selection').addEventListener('click',()=>this.showStory(this.selected));
    $('#close-story').addEventListener('click',()=>{$('#story-detail').hidden=true;});
    $('#photo-button').addEventListener('click',()=>this.setPhoto(!this.photo));
    $('#exit-photo').addEventListener('click',()=>this.setPhoto(false));
    $('#time-slider').addEventListener('input',e=>{this.setPlaying(false);onTime(Number(e.target.value));});
    document.querySelectorAll('[data-hour]').forEach(b=>b.addEventListener('click',()=>{this.setPlaying(false);onTime(Number(b.dataset.hour));}));
    $('#time-play').addEventListener('click',()=>this.setPlaying(!this.playing));
    for(const [key,view] of Object.entries(views)) $('#view-list').append(this.placeButton(view.label,view.caption,()=>{onView(key);this.showPanel(null);}));
    $('#scene-date').textContent=new Intl.DateTimeFormat('en',{month:'2-digit',day:'2-digit'}).format(new Date()).replace('/','.');
  }
  placeButton(name,subtitle,action,index='') {
    const button=document.createElement('button');
    if(index){const n=document.createElement('span');n.className='place-index';n.textContent=index;button.append(n);}
    const text=document.createElement('span'),title=document.createElement('b'),small=document.createElement('small');
    title.textContent=name;small.textContent=subtitle;text.append(title,small);button.append(text);
    const arrow=document.createElement('span');arrow.className='place-arrow';arrow.textContent='↗';button.append(arrow);
    button.addEventListener('click',action);return button;
  }
  setData(buildings,amenities=[]) {
    this.buildings=buildings;this.amenities=amenities;
    $('#canteen-count').textContent=amenities.filter(p=>p.type==='canteen').length;
    $('#bus-stop-count').textContent=amenities.filter(p=>p.type==='bus_stop').length;
    buildings.filter(b=>b.stories.length).forEach(b=>$('#story-list').append(this.placeButton(b.name_zh||b.name,`${b.stories[0].year} — ${b.stories.at(-1).year}`,()=>{this.onSelect(b);this.showPanel(null);this.showStory(b);})));this.search();
  }
  showPanel(id) {
    document.querySelectorAll('[data-panel]').forEach(b=>{const active=b.dataset.panel===id;$('#'+b.dataset.panel).hidden=!active;b.setAttribute('aria-expanded',String(active));});
    if(id){$('#story-detail').hidden=true;if(innerWidth<=600)$('#selection').hidden=true;}
    this.onPanel(id);
  }
  search() {
    const query=$('#search').value.trim(),results=$('#search-results'),landmarks=$('#landmarks');results.replaceChildren();landmarks.replaceChildren();results.hidden=!query;landmarks.hidden=!!query;
    const root=query?results:landmarks;
    const pool=this.category==='building'?this.buildings:this.category==='all'?[...this.amenities,...this.buildings]:this.amenities.filter(p=>p.type===this.category);
    const matches=query?searchBuildings(pool,query,80):this.category==='all'?this.amenities:this.category==='building'?featuredIds.map(id=>this.buildings.find(b=>b.id===id)).filter(Boolean):pool;
    $('#places-summary').textContent=query?`${matches.length} 个搜索结果`:`${this.amenities.filter(p=>p.type==='canteen').length} 处食堂 · ${this.amenities.filter(p=>p.type==='bus_stop').length} 处公交站`;
    if(!matches.length){const p=document.createElement('p');p.className='empty-results';p.textContent='没有找到这个地点。试试中文简称或英文。';root.append(p);}
    for(const b of matches){const category=b.poi?(b.type==='canteen'?'食堂':'公交站'):'';root.append(this.placeButton(b.name_zh||b.name,[category,b.name!==b.name_zh?b.name:''].filter(Boolean).join(' · '),()=>{this.onSelect(b);this.showPanel(null);$('#search').blur();}));}
  }
  showBuilding(b) {
    this.selected=b;$('#selection').hidden=!b;$('#story-detail').hidden=true;if(!b)return;
    $('#selection').classList.toggle('ecology-card',!!b.ecology);
    document.querySelector('#selected-ecology')?.remove();
    if(b.ecology){this.showEcology(b);return;}
    $('#selected-type').textContent=b.poi?(b.type==='canteen'?'食堂 · DINING':'公交站 · BUS STOP'):b.type.toUpperCase();$('#selected-name').textContent=b.name_zh||b.name;$('#selected-en').textContent=b.name!==b.name_zh?b.name:'';
    $('#selected-description').textContent=b.description;$('#selected-year').hidden=!b.year;$('#selected-year').textContent=b.year?`Built ${b.year}`:'';
    $('#selected-height').textContent=Number.isFinite(b.height_m)?`模型 ${b.height_m.toFixed(1)} m`:'';
    $('#selected-height').hidden=!!b.poi;
    $('#selected-source').textContent=({estimated:'用途估算',levels:'楼层推算',height_tag:'地图标注',lidar_photo_estimate:'高程与照片估算'})[b.height_source]||'模型数据';
    if(b.poi)$('#selected-source').textContent=b.locationNote||'位置标记 · 非实时营运信息';
    const source=$('#selected-link');source.hidden=!b.poi||!b.source;if(b.poi&&b.source){source.href=b.source;source.textContent=(b.type==='bus_stop'?'校方地图':b.sourceLabel||'查看地点来源')+' ↗';}
    const notice=$('#selected-notice'),noticeUrl=b.secondarySources?.find(url=>url.startsWith('https://transport.cuhk.edu.hk/')&&!url.endsWith('.pdf'));notice.hidden=!b.poi||!noticeUrl;if(noticeUrl)notice.href=noticeUrl;
    $('#selected-source').title=b.height_note||'';$('#story-selection').disabled=!b.stories.length;
    $('#story-selection').hidden=!!b.poi;
    $('#story-selection').title=b.stories.length?'阅读建筑故事':'故事资料待补充';
  }
  showEcology(b){
    $('#selected-type').textContent=b.type==='plant'?'CAMPUS FLORA · 区域观察':'LAKE ECOLOGY · 生态解说';
    $('#selected-name').textContent=b.name_zh;$('#selected-en').textContent=[b.name,b.scientificName].filter(Boolean).join(' · ');
    $('#selected-description').textContent=b.description;
    $('#selected-year').hidden=true;$('#selected-height').hidden=true;
    $('#selected-source').textContent=`${confidenceLabels[b.confidence]||b.confidence} · 核对 ${b.verifiedAt}`;$('#selected-source').title='核对资料日期，不是实地调查日期';
    $('#selected-link').hidden=true;$('#selected-notice').hidden=true;$('#story-selection').hidden=true;
    const details=document.createElement('div');details.id='selected-ecology';
    const location=document.createElement('p');location.className='muted';location.textContent=b.approximateLocation?`${b.approximateLocation.name} · ${b.approximateLocation.method}`:b.locationNote||'标记表示观察区域，不是个体生物的实测坐标。';details.append(location);
    if(b.notes){const notes=document.createElement('p');notes.className='muted';notes.textContent=b.notes;details.append(notes);}
    for(const source of Array.isArray(b.source)?b.source:[b.source]){
      const a=document.createElement('a');a.href=typeof source==='string'?source:source.url;a.textContent=(source.title||'校方资料来源')+' ↗';a.target='_blank';a.rel='noreferrer';a.className='source-link';details.append(a);
    }
    const notice=document.createElement('p');notice.className='muted';notice.textContent='生态解说样板，非实时监测；植物造型为类型示意，未对全校树木进行精确普查。';details.append(notice);
    $('.building-actions').before(details);
    $('#selected-name').tabIndex=-1;$('#selected-name').focus({preventScroll:true});
  }
  showStory(building,index=0) {
    if(!building?.stories.length)return;
    const story=building.stories[index];$('#story-detail').hidden=false;$('#selection').hidden=true;$('#story-years').replaceChildren();
    building.stories.forEach((s,i)=>{const b=document.createElement('button');b.textContent=s.year;b.classList.toggle('active',i===index);b.addEventListener('click',()=>this.showStory(building,i));$('#story-years').append(b);});
    $('#story-image').hidden=!story.image;$('#story-credit').hidden=!story.image;if(story.image){$('#story-image').src=story.image;$('#story-image').alt=story.imageAlt||story.title;}
    $('#story-title').textContent=story.title;$('#story-text').textContent=story.text;$('#story-source').href=story.source;$('#story-source').textContent=story.sourceLabel+' ↗';this.onPanel();
  }
  setPlaying(value){this.playing=value;$('#time-play').textContent=value?'暂停 Ⅱ':'播放一天 ▷';$('#time-play').setAttribute('aria-pressed',String(value));this.onPlay(value);}
  updateTime(state) {
    const mins=Math.round(state.hours*60)%1440,text=`${String(Math.floor(mins/60)).padStart(2,'0')}:${String(mins%60).padStart(2,'0')}`;
    $('#scene-time').textContent=text;$('#time-value').textContent=text;$('#scene-status').textContent=state.status;
    if(document.activeElement!==$('#time-slider'))$('#time-slider').value=state.hours;
    $('#time-slider').setAttribute('aria-valuetext',text);document.body.classList.toggle('night-ui',state.nightAmount>.65);
  }
  setPhoto(value) {this.photo=value;document.body.classList.toggle('photography',value);$('.photo-controls').hidden=!value;$('#photo-button').setAttribute('aria-pressed',String(value));if(value)this.showPanel(null);this.onPhoto(value);}
}
