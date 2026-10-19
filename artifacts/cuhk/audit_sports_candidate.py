"""Read-only checks against the actual saved Blender sports candidate."""
import bpy,json,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_sports_leveled.blend'))
facilities=json.loads((ROOT/'sports_platforms.json').read_text('utf-8'))['facilities']
levels={str(i):f['surface_z_m'] for f in facilities for i in f['member_ids']}
def co(ob):
    v=np.empty(len(ob.data.vertices)*3,dtype=np.float32);ob.data.vertices.foreach_get('co',v);v=v.reshape(-1,3)
    m=np.array(ob.matrix_world);return v@m[:3,:3].T+m[:3,3]
def triangles(ob):
    ob.data.calc_loop_triangles();f=np.empty(len(ob.data.loop_triangles)*3,dtype=np.int32);ob.data.loop_triangles.foreach_get('vertices',f);return f.reshape(-1,3)
def inside(xy,polygon):
    ring=np.asarray(polygon['coordinates'][0]);x,y=xy[:,0],xy[:,1];mask=np.zeros(len(xy),dtype=bool)
    for a,b in zip(ring[:-1],ring[1:]):
        if abs(b[1]-a[1])<1e-10:continue
        mask^=((a[1]>y)!=(b[1]>y))&(x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0])
    return mask
results=[];exports={}
for ob in bpy.data.collections['05 Water and sport'].objects:
    oid=str(ob.get('osm_id',''))
    if oid not in levels:continue
    v=co(ob);r={'osm_id':oid,'name':ob.name,'z_range_m':float(np.ptp(v[:,2])),'level_error_m':float(np.max(abs(v[:,2]-levels[oid]))),'vertices':len(v)}
    assert r['z_range_m']<1e-5 and r['level_error_m']<2e-6,r
    results.append(r)
    exports['surface_'+oid]=v;exports['surface_faces_'+oid]=triangles(ob)
    if oid in ('955764574','955764585'):exports['track_'+oid]=v;exports['track_faces_'+oid]=triangles(ob)
assert len(results)==11
details=[]
for facility in facilities:
    for name in ['Court paint','Turf stripes','Goal frames','Net mesh']:
        ob=bpy.data.objects.get('Site / '+name)
        if ob is None:continue
        v=co(ob);v=v[inside(v[:,:2],facility['footprint'])]
        if len(v):details.append({'track_id':facility['track_id'],'object':ob.name,'vertices':len(v),'min_above_surface_m':float(v[:,2].min()-facility['surface_z_m']),'max_above_surface_m':float(v[:,2].max()-facility['surface_z_m'])})
adjustment=np.load(ROOT/'sports_path_adjustment.npz')
path=next(ob for ob in bpy.data.collections['04 Roads and paths'].objects if str(ob.get('osm_id'))=='475648093')
v=co(path);exports['path']=v;exports['path_faces']=triangles(path)
local=v-np.asarray(path.matrix_world.translation)
assert np.allclose(local,adjustment['new_vertices'],atol=1e-6,rtol=0)
slab=bpy.data.objects['Road slabs / underside and perimeter'];sv=co(slab)
assert np.array_equal(sv[adjustment['slab_vertex_indices'],:2],adjustment['slab_new_xy'])
metadata=json.loads((ROOT/'sports_path_adjustment.json').read_text('utf-8'))
for shared in metadata['shared_junctions']:
    i=shared['mesh_vertex_index'];assert np.array_equal(local[i],adjustment['old_vertices'][i])
np.savez_compressed(ROOT/'sports_candidate_actual_geometry.npz',**exports)
report={'source':'CUHK_sports_leveled.blend','surfaces':results,'details':details,'path_xy_matches_adjustment':True,'path_slabs_match':True,'shared_path_nodes_unchanged':True}
(ROOT/'sports_actual_mesh_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
