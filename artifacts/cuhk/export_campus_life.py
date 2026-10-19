"""Reuse saved trees and actual road surfaces; export lightweight campus-life inputs."""
import json, math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent.parent / 'cuhk-campus-web/public/campus'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'CUHK_shaw_science_corrected.blend'
before = (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
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
    errors = []
    for a, b in zip(original, original[1:]):
        for j in range(steps := max(1, math.ceil((b-a).length / .75))):
            p = a.lerp(b, j / steps)
            hit, co, _, _ = source.ray_cast(inverse @ Vector((p.x,p.y,1000)), inverse.to_3x3() @ Vector((0,0,-1)))
            assert hit, (source.name, p)
            world = source.matrix_world @ co
            errors.append(abs(world.z-p.z))
            world.z += .035
            if not points or (world-points[-1]).length > .001:
                points.append(world)
    # Leave room inside both end caps; movement ping-pongs along these real points.
    points = points[4:-4]
    assert len(points) > 20
    return {'id': f'{profile["id"]}-{profile["part"]}', 'name': label, 'kind': kind,
            'width': profile['width'], 'osmId': str(profile['id']),
            'points': [web(p) for p in points]}, max(errors)

choices = [(1069, 'University Mall East', 'walk'), (1072, 'University Mall West', 'walk'),
           (758, 'United College Path', 'walk'), (122, 'Sweetheart Path', 'walk'),
           (156, 'Philosophy Path', 'walk'), (214, 'Progress Road', 'walk'),
           (20, 'Central Avenue', 'vehicle'), (14, 'Pond Crescent', 'vehicle'),
           (184, 'Campus Circuit East', 'vehicle'), (53, 'Coastal Cycleway', 'cycle')]
routes = [route(*choice) for choice in choices]

# Furniture is deliberately illustrative. Exclude mapped buildings, sport and water,
# and place it beside the existing path, on the final corrected terrain.
terrain = next(obj for obj in bpy.data.objects if obj.get('display_grid_path'))
grid = np.load(terrain['display_grid_path'])
xs, ys, heights = grid['x'], grid['y'], grid['elevation']
def ground(xy):
    x, y = xy
    u = np.clip((x-xs[0])/(xs[1]-xs[0]), 0, len(xs)-1.000001)
    v = np.clip((y-ys[0])/(ys[1]-ys[0]), 0, len(ys)-1.000001)
    col, row = int(u), int(v)
    fx, fy = u-col, v-row
    z = heights
    return float(z[row,col]*(1-fy)+z[row+1,col]*(fy-fx)+z[row+1,col+1]*fx if fy>=fx else z[row,col]*(1-fx)+z[row,col+1]*(fx-fy)+z[row+1,col+1]*fy)

segments = []
for pi, profile in enumerate(network['profiles']):
    if profile['surface_class'] != 'ground': continue
    pts = np.asarray(profile['points'])[:,:2]
    segments.extend((a,b,pi,profile['width']) for a,b in zip(pts,pts[1:]))
aa = np.array([s[0] for s in segments]); bb = np.array([s[1] for s in segments])
vv = bb-aa; lengths2 = np.maximum((vv*vv).sum(axis=1), 1e-9)
widths = np.array([s[3] for s in segments])
def distances(xy):
    along = np.clip(((xy-aa)*vv).sum(axis=1)/lengths2, 0, 1)
    return np.linalg.norm(xy-aa-along[:,None]*vv, axis=1)

obstacles = []
for feature in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']:
    if feature['kind'] not in ('building','sport','water'): continue
    g = feature['geometry']
    polygons = [g['coordinates']] if g['type']=='Polygon' else g['coordinates'] if g['type']=='MultiPolygon' else []
    for polygon in polygons:
        ring = np.asarray(polygon[0])
        obstacles.append((ring, ring.min(axis=0)-2, ring.max(axis=0)+2))
def clear_site(xy):
    if np.min(distances(xy)-widths/2) < .55: return False
    for ring, lo, hi in obstacles:
        if (xy<lo).any() or (xy>hi).any(): continue
        inside = False
        for a,b in zip(ring, np.roll(ring,-1,axis=0)):
            edge=b-a; along=np.clip(np.dot(xy-a,edge)/max(np.dot(edge,edge),1e-9),0,1)
            if np.linalg.norm(xy-a-along*edge)<1.5: return False
            if (a[1]>xy[1]) != (b[1]>xy[1]) and xy[0] < (b[0]-a[0])*(xy[1]-a[1])/(b[1]-a[1])+a[0]: inside=not inside
        if inside: return False
    return True

furniture = {'benches':[], 'bins':[], 'bicycles':[]}
for pi, _, kind in choices:
    if kind != 'walk' or len(furniture['benches'])>=6: continue
    profile = network['profiles'][pi]
    pts = np.asarray(profile['points'])[:,:2]
    for fraction in [.18,.38,.62,.82]:
        if len(furniture['benches'])>=6: break
        index = min(len(pts)-2, int(len(pts)*fraction))
        tangent = pts[index+1]-pts[index]; tangent/=np.linalg.norm(tangent)
        normal = np.array([-tangent[1],tangent[0]])
        for side in (1,-1):
            center = pts[index]+normal*side*(profile['width']/2+1.12)
            bin_xy = center+tangent*1.5
            checks = [center+dx*tangent+dy*normal for dx in (-.85,.85) for dy in (-.34,.34)]
            if not all(clear_site(q) for q in [center,bin_xy,*checks]): continue
            levels = [ground(q) for q in checks]
            if max(levels)-min(levels)>.15: continue
            if any(np.linalg.norm(center-np.array([r['position'][0],-r['position'][2]]))<14 for r in furniture['benches']): continue
            yaw = math.atan2(tangent[1],tangent[0])+(math.pi if side<0 else 0)
            furniture['benches'].append({'position':web([*center,max(levels)+.006]),'yaw':round(yaw,6)})
            furniture['bins'].append({'position':web([*bin_xy,ground(bin_xy)+.006]),'yaw':round(yaw,6)})
            bike_xy = center-tangent*2.6
            if len(furniture['bicycles'])<3 and clear_site(bike_xy):
                furniture['bicycles'].append({'position':web([*bike_xy,ground(bike_xy)+.02]),'yaw':round(math.atan2(tangent[0],-tangent[1]),6)})
            break
assert len(furniture['benches']) == 6, furniture

# Each original lamp head is 8 side quads plus one 8-vertex cap.
# Select at most 40 existing lamps; validate a shallow tangent patch against
# the actual road. No new pole, light source, or hidden point light is added.
heads = bpy.data.objects['Site / Lamp heads']
head_points = np.array([tuple(heads.matrix_world@v.co) for v in heads.data.vertices])
assert len(head_points)%40==0
lamp_centers = head_points.reshape(-1,40,3).mean(axis=1)
lamp_centers = sorted(lamp_centers, key=lambda q:q[0]*q[0]+q[1]*q[1])
lamp_pools = []
lamp_errors = []
for center in lamp_centers:
    if len(lamp_pools)>=40: break
    k = int(np.argmin(distances(center[:2])))
    pi = segments[k][2]
    if pi not in roads or widths[k]<4: continue
    source = roads[pi]; inverse = source.matrix_world.inverted()
    tangent = vv[k]/math.sqrt(lengths2[k]); normal = np.array([-tangent[1],tangent[0]])
    # Narrow ellipse remains inside the carriageway, near the existing head.
    xy = center[:2] - normal * np.dot(center[:2]-(aa[k]+bb[k])/2,normal)*.35
    offsets = [np.zeros(2)] + [(tangent*math.cos(a)*2.6+normal*math.sin(a)*.72)*r for r in (.33,.67,1) for a in np.linspace(0,2*math.pi,25)[:-1]]
    samples = []
    for offset in offsets:
        q=xy+offset
        hit,co,_,_=source.ray_cast(inverse@Vector((q[0],q[1],1000)),inverse.to_3x3()@Vector((0,0,-1)))
        if not hit: break
        samples.append((source.matrix_world@co).z)
    if len(samples)!=len(offsets): continue
    matrix = np.column_stack((np.array(offsets),np.ones(len(offsets))))
    a,b,c = np.linalg.lstsq(matrix,np.array(samples),rcond=None)[0]
    residual = np.array(samples)-matrix@np.array([a,b,c])
    if np.ptp(residual)>.065: continue
    top = c+residual.max()+.022
    basis = Matrix.Identity(4)
    basis.col[0] = Vector((tangent[0]*2.6,tangent[1]*2.6,(a*tangent[0]+b*tangent[1])*2.6,0))
    basis.col[1] = Vector((normal[0]*.72,normal[1]*.72,(a*normal[0]+b*normal[1])*.72,0))
    basis.col[2] = Vector((-a,-b,1,0)); basis.translation = Vector((xy[0],xy[1],top))
    transform = conversion@basis@conversion.inverted()
    lamp_pools.append([round(transform[row][col],6) for col in range(4) for row in range(4)])
    lamp_errors.append(float(np.ptp(residual)))
assert 32<=len(lamp_pools)<=48, len(lamp_pools)

trees = list(bpy.data.collections['09 Mapped vegetation / illustrative crowns'].objects)
template_names = list(dict.fromkeys(tree.data.name for tree in trees))
tree_rows = []
for tree in trees:
    transform = conversion @ tree.matrix_world @ conversion.inverted()
    tree_rows.append([template_names.index(tree.data.name), *[round(transform[row][col], 6) for col in range(4) for row in range(4)]])

# Bake existing per-face canopy colours into a single vertex-colour material.
# This keeps original silhouettes, but changes 40 primitive draws into 8 batches.
material = bpy.data.materials.new('Campus trees / original vertex colours')
material.use_nodes = True
nodes = material.node_tree.nodes
bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
bsdf.inputs['Roughness'].default_value = .88
color = nodes.new('ShaderNodeVertexColor')
color.layer_name = 'COLOR_0'
material.node_tree.links.new(color.outputs['Color'], bsdf.inputs['Base Color'])
copies = []
triangles = {}
for index, name in enumerate(template_names):
    source = next(tree for tree in trees if tree.data.name == name)
    for lod in ('near', 'far'):
        mesh = source.data.copy()
        colors = mesh.color_attributes.new(name='COLOR_0', type='FLOAT_COLOR', domain='CORNER')
        for polygon in mesh.polygons:
            value = mesh.materials[polygon.material_index].diffuse_color
            for li in polygon.loop_indices:
                colors.data[li].color = value
        mesh.materials.clear()
        mesh.materials.append(material)
        obj = bpy.data.objects.new(f'tree_{index}_{lod}', mesh)
        bpy.context.scene.collection.objects.link(obj)
        if lod == 'far':
            modifier = obj.modifiers.new('Distant crown silhouette', 'DECIMATE')
            modifier.ratio = .28
            modifier.use_collapse_triangulate = True
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.data.validate(clean_customdata=False)
        obj.data.update()
        obj.data.calc_loop_triangles()
        triangles[obj.name] = len(obj.data.loop_triangles)
        copies.append(obj)
bpy.ops.object.select_all(action='DESELECT')
for obj in copies:
    obj.select_set(True)
bpy.context.view_layer.objects.active = copies[0]
bpy.ops.export_scene.gltf(filepath=str(OUT / 'vegetation.glb'), export_format='GLB', use_selection=True,
                         export_yup=True, export_extras=True, export_normals=True,
                         export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
                         export_draco_position_quantization=16)
life = {'illustrative': True,
        'note': 'Illustrative campus activity, not live or measured traffic. Original OSM paths sampled on the final saved road mesh; existing trees reused without duplicating them.',
        'coordinates': 'Three.js metres: X east / Y HKPD elevation / Z south',
        'peopleCount':24, 'carCount':2, 'bicycleCount':2, 'birdCount':6,
        'paths': [row[0] for row in routes], 'treeInstances': tree_rows,
        'furniture':furniture, 'lampPools':lamp_pools,
        'furnitureNote':'Illustrative path-side benches, bins and parked bicycles; positions are not surveyed. Existing mapped sport/water/building footprints and road carriageways are excluded.',
        'treeTemplates': [{'near':f'tree_{i}_near','far':f'tree_{i}_far'} for i in range(8)]}
(OUT / 'life.json').write_text(json.dumps(life, ensure_ascii=False, separators=(',',':')), 'utf-8')
assert before == (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)
report = {'source':str(SOURCE), 'source_unchanged':True, 'trees':len(tree_rows), 'templates':triangles,
          'path_count':len(routes), 'samples':sum(len(row[0]['points']) for row in routes),
          'all_path_samples_hit_saved_road_mesh':True, 'surface_offset_m':.035,
          'maximum_difference_from_raw_route_z_m': max(row[1] for row in routes),
          'illustrative_furniture':{key:len(value) for key,value in furniture.items()},
          'existing_lamp_light_pools':len(lamp_pools), 'light_pool_maximum_plane_residual_span_m':max(lamp_errors),
          'vegetation_bytes':(OUT/'vegetation.glb').stat().st_size, 'life_json_bytes':(OUT/'life.json').stat().st_size}
(ROOT / 'audits/digital_campus/campus_life_export.json').write_text(json.dumps(report, indent=2), 'utf-8')
print('CAMPUS_LIFE_EXPORT',json.dumps(report),flush=True)
