import bpy,json,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_roads_graded.blend'))
features={str(f['id']):f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']}
records=[]
for ob in bpy.data.collections['05 Water and sport'].objects:
    if ob.type!='MESH': continue
    oid=str(ob.get('osm_id','')); f=features.get(oid,{})
    if f.get('kind')!='sport':continue
    co=np.empty(len(ob.data.vertices)*3,dtype=np.float64);ob.data.vertices.foreach_get('co',co);co=co.reshape(-1,3)
    mat=np.array(ob.matrix_world);co=co@mat[:3,:3].T+mat[:3,3]
    r={'name':ob.name,'osm_id':oid,'tags':f['tags'],'geometry':f['geometry']['type'],'vertices':len(co),'xyz_min':co.min(0).tolist(),'xyz_max':co.max(0).tolist(),'z_range_m':float(np.ptp(co[:,2])),'materials':[x.name for x in ob.data.materials]}
    records.append(r)
    print('SPORT',json.dumps(r,ensure_ascii=False),flush=True)
details=[]
for ob in bpy.data.collections['08 Site details'].objects:
    if ob.type!='MESH':continue
    co=np.empty(len(ob.data.vertices)*3,dtype=np.float64);ob.data.vertices.foreach_get('co',co);co=co.reshape(-1,3)
    mat=np.array(ob.matrix_world);co=co@mat[:3,:3].T+mat[:3,3]
    details.append({'name':ob.name,'vertices':len(co),'min':co.min(0).tolist(),'max':co.max(0).tolist(),'materials':[x.name for x in ob.data.materials]})
print('DETAILS',json.dumps(details,ensure_ascii=False),flush=True)
(ROOT/'sports_readonly_audit.json').write_text(json.dumps({'sports':records,'detail_objects':details},ensure_ascii=False,indent=2),encoding='utf-8')
