"""Keep unresolved source-height conflicts inspectable in the delivered Blend."""
import bpy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_connected_roads.blend'))
audit=json.loads((ROOT/'road_surface_after.json').read_text('utf-8'))
checks=bpy.data.collections.get('13 Road levels to verify')
if checks is None:
    checks=bpy.data.collections.new('13 Road levels to verify');bpy.context.scene.collection.children.link(checks)
by_name={o.name:o for o in bpy.data.collections['04 Roads and paths'].objects}
for row in audit['all']:
    ob=by_name[row['object']]
    ob['terrain_probe_count']=row['probe_count'];ob['buried_terrain_probes']=row['buried_probes'];ob['minimum_sampled_terrain_clearance_m']=row['min_clearance_m']
    if row['buried_probes']:
        ob['quality_note']='Local intersection with old display terrain. Elevated or positive-layer route; verify against official 3D levels and detailed terrain. Not a validated bridge deck.'
        if ob.name not in checks.objects:checks.objects.link(ob)
checks['note']='Linked references to residual elevated/positive-layer road objects. This collection does not create new geometry or change appearance.'
scene=bpy.context.scene
scene['road_surface_audit']=json.dumps({k:v for k,v in audit.items() if k not in ('all','worst')},ensure_ascii=False)
scene['data_upgrade_report']='DETAILED_DATA_AND_ROADS.md'
scene['terrain_quality_note']='Current display terrain still uses 5m source. Deepest new illustrative cut 17.52m at building/below-ground access conflict (-255,240). New 0.5m terrain is supplied separately; do not treat cuts as surveyed ground.'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_connected_roads.blend'))
print('ROAD_QUALITY_TAGGED',len(checks.objects))
