import { Raycaster, Vector2, Vector3, Box3, Color } from 'three';
const visible = object => { for(let o=object;o;o=o.parent)if(!o.visible)return false;return true; };

export class BuildingInteraction {
  constructor({camera,buildings,timeSystem,requestRender}) {
    Object.assign(this,{camera,timeSystem,requestRender});this.meshes=new Map();this.roots=new Map();this.highlights=[];this.selected=null;this.hovered=null;
    this.ray=new Raycaster();this.pointer=new Vector2();this.point=new Vector3();this.tint=new Color('#c1ccb9');
    this.boxes=buildings.map(b=>({id:b.id,box:new Box3().setFromCenterAndSize(new Vector3(...b.position),new Vector3(...b.size))}));
  }
  register(root) {
    const meshes=[];root.traverse(object=>{if(!object.isMesh)return;let node=object,id;
      while(node&&!id){id=node.userData.osm_id||node.name.match(/web_building_(\d+)/)?.[1];node=node.parent;}
      if(!id)return;id=String(id);object.userData.buildingId=id;if(!this.meshes.has(id))this.meshes.set(id,new Set());this.meshes.get(id).add(object);meshes.push(object);
    });this.roots.set(root,meshes);this.refresh();
  }
  unregister(root) {this.clearHighlights();for(const mesh of this.roots.get(root)||[]){const set=this.meshes.get(mesh.userData.buildingId);set.delete(mesh);if(!set.size)this.meshes.delete(mesh.userData.buildingId);}this.roots.delete(root);this.refresh();}
  pick(x,y) {
    this.pointer.set(x/innerWidth*2-1,-y/innerHeight*2+1);this.ray.setFromCamera(this.pointer,this.camera);
    const candidates=[];for(const item of this.boxes){if(this.ray.ray.intersectBox(item.box,this.point))candidates.push({id:item.id,distance:this.ray.ray.origin.distanceToSquared(this.point)});}
    candidates.sort((a,b)=>a.distance-b.distance);
    const objects=candidates.slice(0,6).flatMap(item=>[...(this.meshes.get(item.id)||[])].filter(visible));
    return this.ray.intersectObjects(objects,false)[0]?.object.userData.buildingId||null;
  }
  setSelected(id){this.selected=id;this.hovered=null;this.refresh();}
  setHovered(id){if(id===this.hovered)return;this.hovered=id;this.refresh();}
  clearHighlights(){for(const h of this.highlights){this.timeSystem.unregisterModel(h.token);h.mesh.material=h.original;h.materials.forEach(m=>m.dispose());}this.highlights=[];}
  refresh() {
    this.clearHighlights();
    for(const id of new Set([this.selected,this.hovered].filter(Boolean)))for(const mesh of this.meshes.get(id)||[]){
      const original=mesh.material,materials=(Array.isArray(original)?original:[original]).map(m=>{
        const copy=m.clone(),base=this.timeSystem.materials.get(m);
        copy.onBeforeCompile=m.onBeforeCompile;copy.customProgramCacheKey=m.customProgramCacheKey;
        // A night-time clone must retain the original daylight emission baseline.
        if(base?.color&&copy.emissive){copy.emissive.copy(base.color);copy.emissiveIntensity=base.intensity;}
        copy.color?.lerp(this.tint,id===this.selected? .07:.035);return copy;
      });
      mesh.material=Array.isArray(original)?materials:materials[0];
      const token={traverse:fn=>fn({isMesh:true,material:materials})};this.timeSystem.registerModel(token);this.highlights.push({mesh,original,materials,token});
    }this.requestRender();
  }
}
