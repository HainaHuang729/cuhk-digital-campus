"""Run existing road audit then check sports planes in the same saved model."""
import runpy
import json
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT/'audit_road_surfaces_v3.py'),run_name='__main__')

facilities=json.loads((ROOT/'sports_platforms.json').read_text('utf-8'))['facilities']
levels={str(i):f['surface_z_m'] for f in facilities for i in f['member_ids']}
rows=[]
depsgraph=bpy.context.evaluated_depsgraph_get()
for obj in bpy.data.collections['05 Water and sport'].objects:
    oid=str(obj.get('osm_id',''))
    if oid not in levels or obj.type!='MESH':continue
    evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
    values=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',values)
    matrix=np.asarray(evaluated.matrix_world,dtype=np.float64)
    world=values.reshape(-1,3)@matrix[:3,:3].T+matrix[:3,3]
    row={'osm_id':oid,'object':obj.name,'vertices':len(world),'z_range_m':float(np.ptp(world[:,2])),'actual_level_hkpd_m':float(np.median(world[:,2])),'expected_level_hkpd_m':levels[oid],'max_level_error_m':float(np.max(abs(world[:,2]-levels[oid])))}
    evaluated.to_mesh_clear()
    row['pass']=row['z_range_m']<1e-5 and row['max_level_error_m']<2e-6
    rows.append(row)
result={'source':bpy.data.filepath,'status':'complete','surfaces':rows,'surface_count':len(rows),'all_planar_and_at_expected_levels':len(rows)==11 and all(r['pass'] for r in rows)}
(ROOT/'audits/shaw_sports_planarity_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print('SHAW_SPORTS_AUDIT',json.dumps(result),flush=True)
assert result['all_planar_and_at_expected_levels']
