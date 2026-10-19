"""Give each stadium one survey-derived level, including its surface and fittings."""
import bpy,json,sys,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from detail_site import apply_site_details
from prepare_road_grading import load_network,height_sampler

def coords(ob):
    v=np.empty(len(ob.data.vertices)*3,dtype=np.float32)
    ob.data.vertices.foreach_get('co',v)
    return v.reshape(-1,3)

def sampler(filename):
    d=np.load(ROOT/filename);xs,ys,z=d['x'],d['y'],d['elevation'];step=xs[1]-xs[0]
    def height(x,y):
        u=np.clip((np.asarray(x)-xs[0])/step,0,len(xs)-1.00001)
        v=np.clip((ys[0]-np.asarray(y))/step,0,len(ys)-1.00001)
        a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
        return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
    return height

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_roads_graded.blend'))
scene=bpy.context.scene
facilities=json.loads((ROOT/'sports_platforms.json').read_text('utf-8'))['facilities']
fits=json.loads((ROOT/'sports_infield_fit.json').read_text('utf-8'))['facilities']
fit_by_id={str(oid):f for f in fits for oid in f['member_ids']}
levels={str(oid):f['surface_z_m'] for f in facilities for oid in f['member_ids']}
for f in facilities:levels[str(f['track_id'])]=f['surface_z_m']
road_hashes={o.name:hashlib.sha256(coords(o).tobytes()).hexdigest() for o in bpy.data.collections['04 Roads and paths'].objects}
road_furniture={n:coords(bpy.data.objects[n]).copy() for n in ('Site / Road paint','Site / Curbs')}
adjustment=np.load(ROOT/'sports_path_adjustment.npz')
path=next(o for o in bpy.data.collections['04 Roads and paths'].objects if str(o.get('osm_id',''))=='475648093')
assert np.array_equal(coords(path),adjustment['old_vertices'].astype(np.float32))
path.data.vertices.foreach_set('co',adjustment['new_vertices'].astype(np.float32).ravel());path.data.update()
path['sports_edge_adjustment']='Local outward shift at stadium north bend; width, heights and shared junctions retained.'
slab=bpy.data.objects['Road slabs / underside and perimeter'];slab_co=coords(slab)
slab_co[adjustment['slab_vertex_indices'],:2]=adjustment['slab_new_xy']
slab.data.vertices.foreach_set('co',slab_co.ravel());slab.data.update()
report=[]
for ob in bpy.data.collections['05 Water and sport'].objects:
    oid=str(ob.get('osm_id',''))
    if oid not in levels:continue
    v=coords(ob);m=np.array(ob.matrix_world);world=v@m[:3,:3].T+m[:3,3]
    before=float(np.ptp(world[:,2]));world[:,2]=levels[oid]
    if oid in fit_by_id:
        fit=fit_by_id[oid];origin=np.asarray(fit['center_xy'])
        world[:,:2]=origin+(world[:,:2]-origin)*fit['scale']
    inv=np.linalg.inv(m);v=(world@inv[:3,:3].T+inv[:3,3]).astype(np.float32)
    ob.data.vertices.foreach_set('co',v.ravel());ob.data.update()
    ob['sports_surface_hkpd_m']=levels[oid]
    ob['surface_method']='Single planar facility level from median official DTM; illustrative grading, not surveyed finished floor.'
    assert np.ptp(v[:,2])<1e-4
    report.append({'osm_id':oid,'object':ob.name,'old_z_range_m':before,'new_z_range_m':float(np.ptp(v[:,2])),'surface_z_m':levels[oid]})

d=np.load(ROOT/'terrain_sports_leveled_1m.npz')
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o)
v=coords(terrain);v[:,2]=d['elevation'].ravel();terrain.data.vertices.foreach_set('co',v.ravel());terrain.data.update()
terrain['display_grid_path']=str(ROOT/'terrain_sports_leveled_1m.npz')
terrain['sports_grading']='Two stadiums with constant planar playing surface, full infield and feathered outer shoulder; existing road clearance retained.'
ground=sampler('terrain_sports_leveled_1m.npz')
old_ground=sampler('terrain_roads_graded_1m.npz')
sport_ground=sampler('terrain_refined_display.npz')
network,junctions,segments=load_network();road_height=height_sampler(junctions,segments)
def furniture_height(x,y,oid):
    hz=road_height(x,y,oid) if str(oid) in segments else old_ground(x,y)
    return hz-.8-.002*(int(oid)%101)
clearance={}
for j in network['junctions']:
    if j['degree']<3:continue
    radius=max(r['width'] for r in j['incident_roads'])/2+1
    for oid in j['osm_way_ids']:clearance.setdefault(str(oid),[]).append((j['xyz'][:2],radius))
apply_site_details(height_fn=sport_ground,road_height_fn=furniture_height,junction_clearance=clearance,sports_surfaces=levels,sports_infield_fit=fit_by_id)
for ob in bpy.data.collections['09 Mapped vegetation / illustrative crowns'].objects:
    ob.location.z+=float(ground(ob.location.x,ob.location.y)-old_ground(ob.location.x,ob.location.y))
for name,v in road_furniture.items():assert np.array_equal(coords(bpy.data.objects[name]),v),name
for name,h in road_hashes.items():
    if name!=path.name:assert hashlib.sha256(coords(bpy.data.objects[name]).tobytes()).hexdigest()==h,name
assert np.array_equal(coords(path)[:,2],adjustment['old_vertices'][:,2].astype(np.float32))
scene['sports_revision']='Running tracks, infields, lane lines, turf and goals use common per-stadium levels. See SPORTS_LEVELING.md.'
(ROOT/'sports_surface_flatness.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_sports_leveled.blend'))
print('SPORTS_LEVELING_READY',len(report),flush=True)
