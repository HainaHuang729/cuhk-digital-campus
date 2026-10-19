"""Regrade mapped road profiles and export readable Chinese building label views."""
import bpy,json,sys,math
import numpy as np
from pathlib import Path
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
bpy.ops.wm.open_mainfile(filepath=str(root/'CUHK_refined.blend'))
scene=bpy.context.scene
source={o.name:len(o.data.vertices) for o in bpy.data.objects if o.type=='MESH' and 'height_source' in o}
data=json.loads((root/'smooth_road_profiles.json').read_text('utf-8'));profiles={}
for p in data['profiles']:profiles.setdefault(str(p['id']),[]).append(np.array(p['points'],dtype=np.float64))
grid=np.load(root/'terrain_roads_smoothed.npz');oldgrid=np.load(root/'terrain_refined_display.npz');xs,ys=grid['x'],grid['y']
def sample(x,y,z):
    u=np.clip((np.asarray(x)-xs[0])/5,0,len(xs)-1.00001);v=np.clip((ys[0]-np.asarray(y))/5,0,len(ys)-1.00001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
def ground(x,y):return sample(x,y,grid['elevation'])
def original_ground(x,y):return sample(x,y,oldgrid['elevation'])
def project_height(x,y,oid):
    lines=profiles.get(str(oid))
    if not lines:return original_ground(x,y)
    shape=np.broadcast(np.asarray(x),np.asarray(y)).shape
    xx,yy=np.broadcast_arrays(x,y);q=np.column_stack((xx.ravel(),yy.ravel()))
    a=np.concatenate([p[:-1] for p in lines]);b=np.concatenate([p[1:] for p in lines]);v=b[:,:2]-a[:,:2];den=np.maximum(np.sum(v*v,axis=1),1e-12)
    result=[]
    for start in range(0,len(q),256):
        pt=q[start:start+256];t=np.clip(np.sum((pt[:,None,:]-a[None,:,:2])*v[None,:,:],axis=2)/den,0,1)
        d=np.sum((pt[:,None,:]-(a[None,:,:2]+t[:,:,None]*v))**2,axis=2);k=np.argmin(d,axis=1);r=np.arange(len(pt));frac=t[r,k]
        result.extend((a[k,2]*(1-frac)+b[k,2]*frac-.65).tolist())
    return np.asarray(result).reshape(shape)
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o)
co=np.empty(len(terrain.data.vertices)*3,dtype=np.float32);terrain.data.vertices.foreach_get('co',co);co=co.reshape(-1,3);co[:,2]=grid['elevation'].ravel();terrain.data.vertices.foreach_set('co',co.ravel());terrain.data.update()
terrain['road_refinement']='Connected smooth longitudinal road profiles, planar cross sections, blended road shoulders; visual regrading only.'
count=0
for o in bpy.data.collections['04 Roads and paths'].objects:
    if o.type!='MESH' or str(o.get('osm_id')) not in profiles:continue
    oid=str(o['osm_id']);co=np.empty(len(o.data.vertices)*3,dtype=np.float32);o.data.vertices.foreach_get('co',co);co=co.reshape(-1,3)
    co[:,2]=project_height(co[:,0],co[:,1],oid)+.8+.002*(int(oid)%101);o.data.vertices.foreach_set('co',co.ravel());o.data.update()
    for poly in o.data.polygons:poly.use_smooth=True
    o['surface_refinement']='Mapped XY alignment retained; smoothed connected longitudinal profile and level cross-section'
    count+=1
from detail_site import apply_site_details
site=apply_site_details(height_fn=original_ground,road_height_fn=project_height)
for o in bpy.data.collections['09 Mapped vegetation / illustrative crowns'].objects:
    o.location.z=float(ground(o.location.x,o.location.y))-.8
assert all(len(bpy.data.objects[k].data.vertices)==v for k,v in source.items())

scene.render.engine='CYCLES';scene.cycles.samples=128;scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.012;scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    if any(d.type=='OPTIX' for d in prefs.devices):
        for d in prefs.devices:d.use=d.type=='OPTIX'
        scene.cycles.device='GPU'
except Exception as e:print('CPU fallback',e,flush=True)
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.resolution_percentage=100
from building_labels import apply_building_labels
scene.camera=bpy.data.objects['Camera / core architectural detail'];scene.render.resolution_x=3600;scene.render.resolution_y=2700
bpy.context.view_layer.update()
stats={'roads':data['stats'],'road_objects_updated':count,'site':site,'closeup_labels':apply_building_labels(scene.camera,'closeup')}
scene.render.filepath=str(root/'CUHK_labeled_closeup.png');bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Camera / north-up plan'];scene.render.resolution_x=4000;scene.render.resolution_y=4400
scene.camera.data.ortho_scale=2900;bpy.context.view_layer.update()
stats['plan_labels']=apply_building_labels(scene.camera,'plan')
scene.render.filepath=str(root/'CUHK_labeled_campus_plan.png')
scene['README']='Chinese building labels from OSM names and identifiers. Connected road profiles smoothed with level cross-sections and blended shoulders. These are visual regrading and schematic architecture; source terrain remains unchanged in terrain.npz. See LABELS_AND_ROADS.md.'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
group=bpy.data.collections['10 Building labels / OSM names']
(root/'building_label_inventory.json').write_text(group['label_inventory'],encoding='utf-8')
(root/'labels_roads_stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
print('LABELS_ROADS_STATS',stats,flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(root/'CUHK_labeled_smooth_roads.blend'))
bpy.ops.render.render(write_still=True)
print('LABELS_ROADS_COMPLETE',flush=True)
