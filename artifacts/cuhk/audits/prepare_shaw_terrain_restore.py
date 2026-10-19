"""Restore only the Shaw uphill pad; preserve a 3m collar around every road top."""
import json
import sys
from pathlib import Path
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import numpy as np
import shapely
from shapely.geometry import shape, LineString, box

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
base=np.load(ROOT/'terrain_sports_leveled_1m.npz')
survey=np.load(ROOT/'terrain_survey_1m.npz')
assert np.array_equal(base['x'],survey['x']) and np.array_equal(base['y'],survey['y'])
feature=next(f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'] if f['id']==107139044)
foot=shape(feature['geometry']);coords=list(foot.exterior.coords)
rear=shapely.union_all([LineString([coords[i],coords[i+1]]) for i in (0,3,4,18,20,22)])
region=rear.buffer(15).intersection(foot.buffer(15))
minx,miny,maxx,maxy=region.bounds
ix=np.flatnonzero((base['x']>=minx-1)&(base['x']<=maxx+1));iy=np.flatnonzero((base['y']>=miny-1)&(base['y']<=maxy+1))
X,Y=np.meshgrid(base['x'][ix],base['y'][iy]);points=shapely.points(X,Y)

roads=np.load(ROOT/'road_mesh_v3.npz');all_vertices=roads['vertices'];all_faces=roads['faces'];records=json.loads((ROOT/'road_mesh_v3.json').read_text('utf-8'))
nearby=[];road_shapes=[]
query=box(minx-10,miny-10,maxx+10,maxy+10)
for rec in records:
    vertices=all_vertices[rec['vertex_start']:rec['vertex_start']+rec['vertex_count']]
    lo=vertices[:,:2].min(axis=0);hi=vertices[:,:2].max(axis=0)
    if not box(*lo,*hi).intersects(query):continue
    faces=all_faces[rec['face_start']:rec['face_start']+rec['face_count']]
    triangles=vertices[faces][:,:,:2]
    # Limit union work to triangles close enough to influence the bounded region.
    local=(triangles[:,:,0].max(axis=1)>=minx-10)&(triangles[:,:,0].min(axis=1)<=maxx+10)&(triangles[:,:,1].max(axis=1)>=miny-10)&(triangles[:,:,1].min(axis=1)<=maxy+10)
    if not local.any():continue
    geometry=shapely.union_all(shapely.polygons(triangles[local]))
    road_shapes.append(geometry);nearby.append({'id':rec['id'],'part':rec['part'],'name':rec['name'],'triangles':int(local.sum())})
road_top=shapely.union_all(road_shapes)
# The only post-v3 shifted road lies at the distant lower stadium, outside this region.
adjustment=json.loads((ROOT/'sports_path_adjustment.json').read_text('utf-8'))
assert not shape(adjustment['new_road_footprint']).buffer(3).intersects(region)
assert all(r['id']!=adjustment['road_id'] for r in nearby)
road_distance=shapely.distance(points,road_top)
rear_distance=shapely.distance(points,rear)
old=base['elevation'][np.ix_(iy,ix)].copy();natural=survey['elevation'][np.ix_(iy,ix)]
def smooth(value):
    value=np.clip(value,0,1);return value*value*(3-2*value)
weight=smooth((15-rear_distance)/10)*smooth((road_distance-3)/5)*smooth((natural-92)/4)
# Restrict to the upper terrace/back of the building. This never raises downhill terrain.
eligible=shapely.contains_xy(region,X,Y)&(natural>=92)&(natural>old)&survey['source_valid'][np.ix_(iy,ix)]
weight=np.where(eligible,weight,0)
new=old+(natural-old)*weight
protected=road_distance<=3
new[protected]=old[protected]
result=base['elevation'].copy();result[np.ix_(iy,ix)]=new
changed=result!=base['elevation']
assert np.array_equal(new[protected],old[protected])
assert not np.any((new-old)<0)
assert np.all(new<=np.maximum(old,natural)+1e-5)
assert np.array_equal(result[~changed],base['elevation'][~changed])
# No affected triangle can reach a road surface: every moved grid vertex is >3m
# from a road top, exceeding the terrain cell diagonal of sqrt(2)m.
assert np.min(road_distance[new!=old])>3
assert np.all(rear_distance[new!=old]<15)
np.savez_compressed(OUT/'terrain_shaw_science_corrected_1m.npz',x=base['x'],y=base['y'],elevation=result)
def quantile(values):return dict(zip(['min','p05','p25','p50','p75','p95','max'],np.quantile(values,[0,.05,.25,.5,.75,.95,1]).round(4).tolist())) if values.size else {}
report={'source_base':'terrain_sports_leveled_1m.npz','source_restore':'terrain_survey_1m.npz','output':'terrain_shaw_science_corrected_1m.npz','building_osm_id':107139044,'method':'Uphill/back edges within 15m and source DTM >=92m only. Restore toward original survey using cubic feather, full rear-edge weight within 5m and zero at 15m; source-height eligibility feathers from zero at 92m to full at 96m. Protect every road top plus 3m collar exactly; smooth transition from 3m to 8m away from road tops. Road geometry is unchanged.','changed_vertices':int(changed.sum()),'max_raise_m':float(np.max(new-old)),'changed_before':quantile(old[new!=old]),'changed_after':quantile(new[new!=old]),'original_survey_at_changed':quantile(natural[new!=old]),'protected_road_vertices_in_window':int(protected.sum()),'protected_road_vertices_exact':bool(np.array_equal(new[protected],old[protected])),'minimum_changed_vertex_distance_to_road_top_m':float(np.min(road_distance[new!=old])),'unchanged_outside_changed_mask':True,'no_lowering':True,'no_changed_source_dtm_below_92m':True,'affected_bounds_local_m':[float(X[new!=old].min()),float(Y[new!=old].min()),float(X[new!=old].max()),float(Y[new!=old].max())],'source_road_mesh':'road_mesh_v3.npz triangles; sports_path_adjustment checked disjoint','nearby_road_parts':nearby,'rear_edges':[],'limitation':'Protected roads and collars may retain the previous local depression. This repair does not regrade or move roads. Survey DTM under buildings is interpolated bare earth, not a surveyed building floor.'}
for edge in (4,20):
    line=LineString([coords[edge],coords[edge+1]])
    mask=shapely.contains_xy(line.buffer(3),X,Y)&~shapely.contains_xy(foot,X,Y)
    report['rear_edges'].append({'edge_index':edge,'before':quantile(old[mask]),'after':quantile(new[mask]),'survey':quantile(natural[mask]),'protected_vertices':int(np.sum(mask&protected)),'vertices':int(mask.sum())})
(OUT/'shaw_terrain_restore_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
