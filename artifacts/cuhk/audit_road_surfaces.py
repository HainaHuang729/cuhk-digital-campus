"""Measure road mesh burial against the actual displayed terrain triangles."""
import bpy,json,sys
import numpy as np
from pathlib import Path
root=Path(__file__).resolve().parent
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
source=root/(args[0] if args else 'CUHK_photo_rebuilt.blend')
bpy.ops.wm.open_mainfile(filepath=str(source))
grid=np.load(root/'terrain_roads_smoothed.npz');xs,ys,z=grid['x'],grid['y'],grid['elevation']
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o)
co=np.empty(len(terrain.data.vertices)*3,dtype=np.float64);terrain.data.vertices.foreach_get('co',co)
z=co.reshape(-1,3)[:,2].reshape(z.shape)
def ground(x,y):
    u=np.clip((x-xs[0])/5,0,len(xs)-1.000001);v=np.clip((ys[0]-y)/5,0,len(ys)-1.000001)
    a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
features={str(f['id']):f for f in json.loads((root/'geodata.json').read_text('utf-8'))['features'] if f['kind']=='road'}
rows=[]
for o in bpy.data.collections['04 Roads and paths'].objects:
    if o.type!='MESH' or o.hide_render:continue
    o.data.calc_loop_triangles();xyz=np.array([o.matrix_world@v.co for v in o.data.vertices]);tris=np.array([list(t.vertices) for t in o.data.loop_triangles])
    if not len(tris):continue
    p=xyz[tris];area=np.abs(np.cross(p[:,1,:2]-p[:,0,:2],p[:,2,:2]-p[:,0,:2]))/2
    select=area>1e-6;p=p[select];area=area[select]
    if not len(p):continue
    probes=np.stack((p.mean(axis=1),(p[:,0]+p[:,1])/2,(p[:,1]+p[:,2])/2,(p[:,2]+p[:,0])/2),axis=1)
    clearance=probes[:,:,2]-ground(probes[:,:,0],probes[:,:,1])
    oid=str(o.get('osm_id'));tags=features.get(oid,{}).get('tags',{})
    bad=clearance<-.05;k=np.unravel_index(np.argmin(clearance),clearance.shape)
    rows.append({'id':oid,'object':o.name,'highway':tags.get('highway'),'bridge':tags.get('bridge'),'layer':tags.get('layer','0'),'surface_class':o.get('surface_class','legacy_unspecified'),'triangles':len(p),'probe_count':int(clearance.size),'buried_probes':int(bad.sum()),'min_clearance_m':round(float(clearance.min()),4),'buried_area_estimate_m2':float((bad.mean(axis=1)*area).sum()),'area_m2':float(area.sum()),'worst_point':probes[k].tolist(),'max_triangle_edge_m':float(max(np.linalg.norm(p[:,1,:2]-p[:,0,:2],axis=1).max(),np.linalg.norm(p[:,2,:2]-p[:,0,:2],axis=1).max()))})
result={'source':str(source),'method':'Four barycentric/edge probes per rendered mesh triangle vs displayed terrain triangles; approximate buried-area fraction, not measured road topology.','roads':len(rows),'roads_with_buried_samples':sum(r['buried_probes']>0 for r in rows),'buried_probe_count':sum(r['buried_probes'] for r in rows),'total_probes':sum(r['probe_count'] for r in rows),'estimated_buried_area_m2':sum(r['buried_area_estimate_m2'] for r in rows),'total_surface_area_m2':sum(r['area_m2'] for r in rows),'worst':sorted(rows,key=lambda r:r['buried_area_estimate_m2'],reverse=True)[:35],'all':rows}
(root/('road_surface_after.json' if args else 'road_surface_before.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('all','worst')},ensure_ascii=False),flush=True)
print(json.dumps(result['worst'][:4],ensure_ascii=False),flush=True)
