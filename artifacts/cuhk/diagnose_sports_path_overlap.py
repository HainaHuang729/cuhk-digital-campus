import json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import shapely
from shapely.geometry import shape,mapping
meshes=json.loads((ROOT/'meshes.json').read_text('utf-8'))
track=next(r for r in meshes if r['id']==955764574)
trackgeo=shapely.union_all([shapely.union_all(shapely.polygons(np.asarray(part['vertices'],dtype=np.float32).astype(float)[np.asarray(part['faces'])])) for part in track['parts']])
mesh=np.load(ROOT/'road_mesh_v3.npz')
road=next(r for r in json.loads((ROOT/'road_mesh_v3.json').read_text('utf-8')) if r['id']=='475648093')
v=mesh['vertices'][road['vertex_start']:road['vertex_start']+road['vertex_count']]
f=mesh['faces'][road['face_start']:road['face_start']+road['face_count']]
roadgeo=shapely.union_all(shapely.polygons(v[f][:,:,:2]))
source=next(r for r in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'] if r['id']==955764574)
line=shape(source['geometry'])
overlap=trackgeo.intersection(roadgeo)
trim=trackgeo.intersection(roadgeo.buffer(.15))
parts=[p for p in shapely.get_parts(overlap) if p.area>1e-5]
r={'track_id':'955764574','road_id':'475648093','actual_mesh_xy_overlap_m2':float(overlap.area),'overlap_bounds':list(overlap.bounds),'overlap_center_xy':[overlap.centroid.x,overlap.centroid.y],'minimum_road_surface_to_track_centerline_m':line.distance(roadgeo),'maximum_track_outer_half_width_intrusion_m':4-line.distance(roadgeo),'recommended_clearance_m':.15,'area_removed_with_15cm_clearance_m2':trim.area,'centerline_crossed_by_15cm_cut':line.intersects(roadgeo.buffer(.15)),'components':[{'area_m2':p.area,'bounds':list(p.bounds),'center_xy':[p.centroid.x,p.centroid.y]} for p in parts],'road_footprint':mapping(roadgeo),'cut_footprint':mapping(roadgeo.buffer(.15))}
(ROOT/'sports_path_overlap.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in r.items() if k not in ('road_footprint','cut_footprint')},ensure_ascii=False,indent=2))
