"""Read the saved campus; extract fixed routes and reusable tree data. Never save it."""
import json, math
from pathlib import Path
from collections import Counter

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'CUHK_shaw_science_corrected.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
stat = (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)
network = json.loads((ROOT / 'road_network_v3.json').read_text('utf-8'))
roads = {int(o['profile_index']): o for o in bpy.data.collections['04 Roads and paths'].objects if 'profile_index' in o}
conversion = Matrix.Rotation(-math.pi / 2, 4, 'X')

def web(point):
    return [round(point[0], 4), round(point[2], 4), round(-point[1], 4)]

def route(profile_index, label, kind):
    profile = network['profiles'][profile_index]
    source = roads[profile_index]
    inverse = source.matrix_world.inverted()
    original = [Vector(p) for p in profile['points']]
    points = []
    max_error = 0.0
    for a, b in zip(original, original[1:]):
        steps = max(1, math.ceil((b-a).length / 1.0))
        for j in range(steps):
            p = a.lerp(b, j / steps)
            hit, co, normal, index = source.ray_cast(inverse @ Vector((p.x,p.y,1000)), inverse.to_3x3() @ Vector((0,0,-1)))
            assert hit, (source.name, p)
            world = source.matrix_world @ co
            max_error = max(max_error, abs(world.z-p.z))
            world.z += .035
            if not points or (world-points[-1]).length > .001:
                points.append(world)
    # Leave room for a smooth turn inside both round road caps.
    points = points[3:-3]
    assert len(points) > 20
    return {'id': f'{profile["id"]}-{profile["part"]}', 'name': label, 'kind': kind,
            'width': profile['width'], 'source_profile_index': profile_index,
            'osm_id': str(profile['id']), 'surface_class': profile['surface_class'],
            'length': round(sum((b-a).length for a,b in zip(points,points[1:])), 3),
            'maximum_centerline_to_mesh_difference_m': round(max_error, 5),
            'points': [web(p) for p in points]}

choices = [(1069, 'University Mall East', 'walk'), (1072, 'University Mall West', 'walk'),
           (758, 'United College Path', 'walk'), (122, 'Sweetheart Path', 'walk'),
           (156, 'Philosophy Path', 'walk'), (214, 'Progress Road', 'walk'),
           (20, 'Central Avenue', 'vehicle'), (14, 'Pond Crescent', 'vehicle'),
           (184, 'Campus Circuit East', 'vehicle'), (53, 'Coastal Cycleway', 'cycle')]
paths = [route(*choice) for choice in choices]
path_data = {'coordinate_system': 'Three.js metres, X east / Y elevation HKPD / Z south',
             'source': 'Existing OSM routes, snapped to actual final Blender road surface. Illustrative traffic, not observed travel data.',
             'surface_clearance_m': .035, 'paths': paths}
(OUT / 'campus_paths.draft.json').write_text(json.dumps(path_data, ensure_ascii=False, separators=(',',':')), 'utf-8')

trees = list(bpy.data.collections['09 Mapped vegetation / illustrative crowns'].objects)
templates = {}
instances = []
for tree in trees:
    key = tree.data.name
    if key not in templates:
        mesh = tree.data
        mesh.calc_loop_triangles()
        positions, normals, colors = [], [], []
        for tri in mesh.loop_triangles:
            color = mesh.materials[tri.material_index].diffuse_color[:3]
            for vi in tri.vertices:
                vertex = mesh.vertices[vi]
                positions.extend(web(vertex.co))
                normals.extend(web(vertex.normal))
                colors.extend(round(v,5) for v in color)
        templates[key] = {'name': key, 'positions': positions, 'normals': normals, 'colors': colors}
    transform = conversion @ tree.matrix_world @ conversion.inverted()
    instances.append({'template': key, 'matrix': [round(transform[row][col], 6) for col in range(4) for row in range(4)]})
tree_data = {'source': 'Original eight shared Blender tree templates and final saved placement; replacement for web_site_09, never an additional layer.',
             'templates': list(templates.values()), 'instances': instances}
(OUT / 'vegetation_instances.draft.json').write_text(json.dumps(tree_data, separators=(',',':')), 'utf-8')

site = bpy.data.collections['08 Site details']
report = {'source': str(SOURCE), 'source_unchanged': True,
          'vegetation': {'trees': len(trees), 'shared_templates': len(templates),
                         'triangles_per_template': {k:len(v['positions'])//9 for k,v in templates.items()},
                         'runtime_replacement': '8 InstancedMesh with vertex colors; remove/hide existing web_site_09 first.'},
          'site_objects': [{'name':o.name, 'vertices':len(o.data.vertices), 'materials':[m.name for m in o.data.materials]} for o in site.objects if o.type=='MESH'],
          'paths': [{k:v for k,v in p.items() if k!='points'} for p in paths],
          'existing_props': ['157 street lamps', 'road curbs and markings', 'sports equipment', 'rooftop equipment', 'entrance canopies'],
          'not_found_in_generation_scripts': ['people','cars','bicycles','birds','benches','bins','hydrants','manholes']}
assert stat == (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)
(OUT / 'campus_life_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
print('CAMPUS_LIFE_AUDIT', json.dumps({'trees':len(trees),'templates':len(templates),'paths':len(paths),'site_objects':len(site.objects)}), flush=True)
