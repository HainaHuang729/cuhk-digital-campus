"""Read-only diagnostic of single-sided visibility in the actual source and FBX."""
import bpy, json, sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from io_scene_fbx import parse_fbx
from export_ue5 import selected_geometry

folder = ROOT / 'ue5' / 'latest'
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'CUHK_sports_leveled.blend'))

def arrays(ob):
    m = ob.data
    v = np.empty((len(m.vertices), 3), np.float64)
    m.vertices.foreach_get('co', v.ravel())
    matrix = np.asarray(ob.matrix_world)
    v = v @ matrix[:3, :3].T + matrix[:3, 3]
    m.calc_loop_triangles()
    f = np.empty((len(m.loop_triangles), 3), np.int32)
    m.loop_triangles.foreach_get('vertices', f.ravel())
    mi = np.empty(len(m.loop_triangles), np.int32)
    m.loop_triangles.foreach_get('material_index', mi)
    return v, f, mi

def stats(v, f):
    cross = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    length = np.linalg.norm(cross, axis=1)
    normal = cross / np.maximum(length[:, None], 1e-30)
    return {'triangles': len(f), 'upward': int((normal[:, 2] > .01).sum()),
            'downward': int((normal[:, 2] < -.01).sum()),
            'horizontal_normal': int((abs(normal[:, 2]) <= .01).sum()),
            'degenerate': int((length < 1e-12).sum()),
            'z_min': float(v[:, 2].min()), 'z_max': float(v[:, 2].max())}, normal

surfaces, facades = [], []
for group, ob in selected_geometry(bpy.context.scene):
    if group not in {'05', '07', '11'} or ob.type != 'MESH':
        continue
    v, f, mi = arrays(ob)
    if group == '05':
        st, _ = stats(v, f)
        surfaces.append({'name': ob.name, 'osm_id': str(ob.get('osm_id', '')), **st,
                         'materials': [m.name for m in ob.data.materials]})
        continue
    glass_indices = [i for i, mat in enumerate(ob.data.materials) if any(word in mat.name.lower() for word in ['glaz', 'glass'])]
    glass = np.isin(mi, glass_indices)
    if not glass.any():
        continue
    gf = f[glass]
    st, normals = stats(v, gf)
    st.update(name=ob.name, osm_id=str(ob.get('osm_id', '')), collection=group,
              glass_materials=[ob.data.materials[i].name for i in glass_indices])
    source = bpy.data.objects.get(ob.get('source_building', ''))
    if source is None:
        oid = str(ob.get('osm_id', ''))
        source = next((o for o in bpy.data.collections['02 Campus buildings'].objects if str(o.get('osm_id', '')) == oid), None)
    if source is not None:
        sv = np.asarray([source.matrix_world @ vertex.co for vertex in source.data.vertices])
        walls = []
        nt = np.asarray(source.matrix_world.to_3x3().inverted().transposed())
        for poly in source.data.polygons:
            n = nt @ np.asarray(poly.normal)
            n /= max(1e-30, np.linalg.norm(n))
            if abs(n[2]) > .02 or len(poly.vertices) != 4:
                continue
            points = sv[list(poly.vertices)]
            low = points[np.argsort(points[:, 2])[:2]]
            u = low[1] - low[0]
            width = np.linalg.norm(u)
            if width < .1:
                continue
            walls.append((low[0], u / width, width, points[:, 2].min(), points[:, 2].max(), n))
        if walls:
            center = v[gf].mean(axis=1)
            best = np.full(len(gf), np.inf)
            outward = np.zeros_like(center)
            for a, u, width, lo, hi, n in walls:
                delta = center - a
                horizontal = delta @ u
                edge_dist = np.maximum(-horizontal, 0) + np.maximum(horizontal - width, 0)
                z_dist = np.maximum(lo - center[:, 2], 0) + np.maximum(center[:, 2] - hi, 0)
                distance = (delta @ n) ** 2 + edge_dist ** 2 + z_dist ** 2
                selected = distance < best
                best[selected] = distance[selected]
                outward[selected] = n
            dot = (normals * outward).sum(axis=1)
            near = best < 4
            st.update(source_building=source.name, near_source_wall_triangles=int(near.sum()),
                      facing_outward=int((near & (dot > .5)).sum()),
                      facing_inward=int((near & (dot < -.5)).sum()),
                      perpendicular=int((near & (abs(dot) <= .5)).sum()))
    facades.append(st)

report = json.loads((folder / 'export_report.json').read_text(encoding='utf-8'))
batch = next(b for b in report['batches'] if b['name'] == 'SM_CUHK_05_001')
root, _ = parse_fbx.parse(str(folder / batch['file']))
models, links = {}, {}
stack = [root]
while stack:
    node = stack.pop()
    stack.extend(node.elems)
    if node.id == b'Model':
        models[node.props[0]] = node.props[1].split(b'\x00')[0].decode()
    if node.id == b'C' and node.props[0] == b'OO':
        links[node.props[1]] = node.props[2]
stack = [root]
fbx_surfaces = []
while stack:
    node = stack.pop()
    stack.extend(node.elems)
    if node.id != b'Geometry' or node.props[-1] != b'Mesh':
        continue
    name = node.props[1].split(b'\x00')[0].decode()
    model_name = models[links[node.props[0]]]
    index = int(model_name.split('Object')[-1])
    v = f = None
    for child in node.elems:
        if child.id == b'Vertices':
            v = np.asarray(child.props[0]).reshape(-1, 3)
        if child.id == b'PolygonVertexIndex':
            raw = np.asarray(child.props[0])
            raw = np.where(raw < 0, -raw - 1, raw)
            f = raw.reshape(-1, 3)
    st, _ = stats(v, f)
    fbx_surfaces.append({'fbx_mesh': name, 'source_object': batch['source_objects'][index]['source_object'], **st})

summary = {'source': 'CUHK_sports_leveled.blend', 'read_only': True,
           'sports_water_objects': len(surfaces),
           'sports_water_downward_triangles': sum(s['downward'] for s in surfaces),
           'sports_water_upward_triangles': sum(s['upward'] for s in surfaces),
           'glazing_objects': len(facades),
           'glazing_facing_inward': sum(s.get('facing_inward', 0) for s in facades),
           'glazing_facing_outward': sum(s.get('facing_outward', 0) for s in facades)}
output = {'summary': summary, 'surfaces': surfaces, 'facades': facades, 'fbx_surfaces': fbx_surfaces,
          'note': 'FBX model rotation is 180 degrees around Z, preserving upward/downward orientation. Facade diagnosis compares glazing normals with the nearest original source wall within 2 meters; ambiguous distant geometry is excluded.'}
(folder / 'surface_normals_diagnosis.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False), flush=True)
print(json.dumps([s for s in surfaces if s['osm_id'] in ['955764574', '955764585'] or any('water' in m.lower() for m in s['materials'])], ensure_ascii=False), flush=True)
