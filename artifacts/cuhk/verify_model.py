"""Read the saved .blend and validate the delivered geometry and its metadata."""
import bpy,bmesh,json,math
from pathlib import Path
root=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(root/'CUHK_terrain_buildings.blend'))
buildings=[o for o in bpy.data.objects if 'height_source' in o]
assert len(buildings)>=370
bad=[]
for o in buildings:
    assert o['height_source'] in ('height_tag','levels','estimated')
    assert 0<o['height_m']<500
    assert all(math.isfinite(v) for p in o.data.vertices for v in p.co)
    bm=bmesh.new(); bm.from_mesh(o.data)
    edges=sum(not e.is_manifold for e in bm.edges)
    if edges: bad.append({'object':o.name,'nonmanifold_edges':edges})
    bm.free()
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o)
assert len(terrain.data.vertices)==481*481
assert abs(terrain.dimensions.x-2400)<.01 and abs(terrain.dimensions.y-2400)<.01
assert bpy.context.scene.unit_settings.scale_length==1
assert len([o for o in bpy.data.objects if o.type=='CAMERA'])==2
result={'building_objects':len(buildings),'terrain_vertices':len(terrain.data.vertices),'terrain_size_m':[2400,2400],'invalid_building_meshes':bad}
(root/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
assert not bad, 'Building meshes must be closed after welding'
