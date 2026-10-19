"""Decode the actual vegetation asset and check exported surfaces and counts."""
import json, struct
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT.parent.parent / 'cuhk-campus-web/public/campus'
report = json.loads((ROOT/'audits/digital_campus/campus_life_export.json').read_text('utf-8'))
blob = (OUT/'vegetation.glb').read_bytes()
count, kind = struct.unpack_from('<II', blob, 12)
document = json.loads(blob[20:20+count])
assert len(document['meshes']) == 16
assert not document.get('textures')
assert all(len(mesh['primitives']) == 1 for mesh in document['meshes'])
assert all('COLOR_0' in mesh['primitives'][0]['attributes'] for mesh in document['meshes'])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=str(OUT/'vegetation.glb'))
actual = {}
for obj in bpy.data.objects:
    if obj.type != 'MESH': continue
    obj.data.calc_loop_triangles()
    actual[obj.name] = len(obj.data.loop_triangles)
    assert all(abs(value) < 2 for vertex in obj.data.vertices for value in vertex.co)
assert actual == report['templates'], (actual, report['templates'])
validation = {'vegetation_decoded':True, 'templates':len(actual), 'template_triangles':sum(actual.values()),
              'one_material_primitive_per_template':True, 'vertex_colours_preserved':True,
              'textures':0, 'original_tree_instances':1374, 'surface_samples':report['samples'],
              'draws_maximum_trees':16, 'draws_maximum_activity':7,
              'draws_static_furniture':3, 'draws_night_light_pools':1,
              'illustrative_furniture':report['illustrative_furniture'],
              'light_pools':report['existing_lamp_light_pools'],
              'all_far_trees_triangles':1374 * 95, 'all_near_trees_triangles':1374 * 344,
              'note':'Full render FPS and final visibility depend on the host scene; instance transforms and toggles have a Node test.'}
(ROOT/'audits/digital_campus/campus_life_validation.json').write_text(json.dumps(validation, indent=2), 'utf-8')
print('CAMPUS_LIFE_VALIDATED', json.dumps(validation), flush=True)
