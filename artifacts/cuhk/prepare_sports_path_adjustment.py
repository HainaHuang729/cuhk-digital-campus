"""Move a short Philosophy Path bend outside the complete running track."""
import json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import shapely
from shapely.geometry import shape,LineString,Point

network=json.loads((ROOT/'road_network_v3.json').read_text('utf-8'))
records=json.loads((ROOT/'road_mesh_v3.json').read_text('utf-8'))
record=next(r for r in records if r['id']=='475648093')
profile=network['profiles'][record['profile_index']]
points=np.asarray(profile['points']);line=LineString(points[:,:2])
ss=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points[:,:2],axis=0),axis=1))]
end=float(ss[42])
source=next(f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'] if f['id']==955764574)
trackline=shape(source['geometry'])
tracks=json.loads((ROOT/'meshes.json').read_text('utf-8'))
track=next(m for m in tracks if m['id']==955764574)
track_shape=shapely.union_all([shapely.union_all(shapely.polygons(np.asarray(p['vertices'],dtype=np.float32).astype(float)[p['faces']])) for p in track['parts']])
mesh=np.load(ROOT/'road_mesh_v3.npz')
old=mesh['vertices'][record['vertex_start']:record['vertex_start']+record['vertex_count']].copy()
faces=mesh['faces'][record['face_start']:record['face_start']+record['face_count']]
def ease(a):
    a=np.clip(a,0,1);return a*a*(3-2*a)

# Keep seven metres around both shared junctions unchanged. The middle offset
# stays constant and the two shoulders transition with zero end derivatives.
weights=ease((ss-7)/12)*ease((end-7-ss)/12)
nearest=shapely.line_interpolate_point(trackline,shapely.line_locate_point(trackline,shapely.points(points[:,:2])))
directions=points[:,:2]-shapely.get_coordinates(nearest)
directions/=np.maximum(np.linalg.norm(directions,axis=1,keepdims=True),1e-9)
station=shapely.line_locate_point(line,shapely.points(old[:,:2]))
for amplitude in np.arange(2.8,4.01,.05):
    shift=directions*weights[:,None]*amplitude
    delta=np.column_stack([np.interp(station,ss,shift[:,axis]) for axis in (0,1)])
    new=old.copy();new[:,:2]+=delta.astype(np.float32)
    geometry=shapely.union_all(shapely.polygons(new[faces][:,:,:2]))
    if geometry.distance(track_shape)>=1.20:break
else:raise AssertionError('The local offset did not clear the full track, 1m verge and 0.20m margin')

tris=new[faces];ab=tris[:,1,:2]-tris[:,0,:2];ac=tris[:,2,:2]-tris[:,0,:2];cross=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
assert np.all(cross>0),('mesh folding after adjustment',int((cross<=0).sum()))
assert np.array_equal(new[:,2],old[:,2])
shared=[]
for j in profile['junction_nodes']:
    xy=points[j['point_index'],:2].astype(np.float32)
    vertex=int(np.argmin(np.linalg.norm(old[:,:2]-xy,axis=1)))
    assert np.linalg.norm(old[vertex,:2]-xy)<1e-5
    assert np.array_equal(new[vertex],old[vertex])
    shared.append({'osm_node_id':j['osm_node_id'],'point_index':j['point_index'],'mesh_vertex_index':vertex,'unchanged':True})
start=2*record['vertex_start'];n=len(old)
slab_indices=np.r_[np.arange(start,start+n),np.arange(start+n,start+2*n)]
np.savez_compressed(ROOT/'sports_path_adjustment.npz',old_vertices=old,new_vertices=new,faces=faces,slab_vertex_indices=slab_indices,slab_new_xy=np.vstack((new[:,:2],new[:,:2])),source_profile_points=points,adjusted_profile_points=np.column_stack((points[:,:2]+shift,points[:,2])))
meta={'road_id':record['id'],'part':record['part'],'profile_index':record['profile_index'],'track_id':'955764574','method':'Continuous per-source-station XY offset along the track outward normal. Smooth 12m transitions with unchanged seven-metre collars around both shared junctions. Z, topology, source cross-section width, shared-node mesh vertices are preserved. Illustrative local alignment correction, not a surveyed route revision.','max_shift_m':float(np.linalg.norm(new[:,:2]-old[:,:2],axis=1).max()),'nominal_path_width_m':record['width'],'track_minimum_gap_m':geometry.distance(track_shape),'track_overlap_m2':geometry.intersection(track_shape).area,'moved_vertices':int(np.sum(np.linalg.norm(new[:,:2]-old[:,:2],axis=1)>1e-5)),'total_vertices':len(old),'shared_junctions':shared,'slab_object':'Road slabs / underside and perimeter','slab_first_vertex_index':start,'slab_vertex_count':2*n,'new_road_footprint':shapely.geometry.mapping(geometry),'terrain_note':'Use the matching sports terrain output after rerunning prepare_sports_platforms.py; the original road trench is restored and the relocated road receives a new protected bed.'}
(ROOT/'sports_path_adjustment.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print('SPORT_PATH_ADJUSTED',json.dumps({k:v for k,v in meta.items() if k!='new_road_footprint'},ensure_ascii=False),flush=True)
