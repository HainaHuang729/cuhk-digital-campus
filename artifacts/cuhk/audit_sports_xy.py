"""Check actual exported sports meshes for XY track/infield intersections."""
import json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import shapely
from shapely.geometry import Polygon
d=np.load(ROOT/'sports_candidate_actual_geometry.npz')
fit=json.loads((ROOT/'sports_infield_fit.json').read_text('utf-8'))['facilities']
data={str(f['id']):f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']}
path=shapely.union_all(shapely.polygons(d['path'][d['path_faces']][:,:,:2]))
checks=[]
for facility in fit:
    oid=facility['track_id']
    track=shapely.union_all(shapely.polygons(d['track_'+oid][d['track_faces_'+oid]][:,:,:2]))
    members=shapely.union_all([shapely.union_all(shapely.polygons(d['surface_'+i][d['surface_faces_'+i]][:,:,:2])) for i in facility['member_ids']])
    core=Polygon(data[oid]['geometry']['coordinates'])
    overlap=track.intersection(members).area
    assert overlap<1e-6,(oid,'infield overlaps actual rubber track',overlap)
    assert core.buffer(-4.299).covers(members),(oid,'less than 0.3m inner-edge margin')
    r={'track_id':oid,'actual_infield_track_overlap_m2':overlap,'actual_min_infield_centerline_clearance_m':core.boundary.distance(members),'actual_min_infield_rubber_clearance_m':track.distance(members),'actual_path_track_overlap_m2':path.intersection(track).area,'actual_path_track_minimum_gap_m':path.distance(track)}
    checks.append(r)
report=json.loads((ROOT/'sports_actual_mesh_audit.json').read_text('utf-8'));report['infield_xy_checks']=checks
(ROOT/'sports_actual_mesh_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks,ensure_ascii=False,indent=2),flush=True)
