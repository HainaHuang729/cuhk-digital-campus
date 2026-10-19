"""Read-only audit of shipped GLBs. No source or production assets are edited."""
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
MODEL = ROOT / 'cuhk-campus-web/public/model'


def inspect(path):
    raw = path.read_bytes()
    magic, version, length, json_length, kind = struct.unpack_from('<4sIIII', raw)
    assert (magic, version, length, kind) == (b'glTF', 2, len(raw), 0x4e4f534a)
    doc = json.loads(raw[20:20 + json_length])
    objects = []
    groups = defaultdict(lambda: dict(triangles=0, primitives=0, nodes=0, position_vertices=0))
    for node in doc.get('nodes', []):
        if 'mesh' not in node:
            continue
        mesh = doc['meshes'][node['mesh']]
        pris = mesh['primitives']
        triangles = sum(doc['accessors'][p['indices']]['count'] // 3 for p in pris)
        vertices = sum(doc['accessors'][p['attributes']['POSITION']]['count'] for p in pris)
        lo = [min(doc['accessors'][p['attributes']['POSITION']]['min'][i] for p in pris) for i in range(3)]
        hi = [max(doc['accessors'][p['attributes']['POSITION']]['max'][i] for p in pris) for i in range(3)]
        # Exporter bakes all transforms into meshes before glTF Y-up conversion.
        assert not any(k in node for k in ('matrix', 'rotation', 'translation', 'scale')), node['name']
        group = node.get('extras', {}).get('category', 'unknown')
        row = dict(name=node.get('name'), category=group, primitives=len(pris), triangles=triangles,
                   position_vertices=vertices, bounds_min=lo, bounds_max=hi, extras=node.get('extras', {}))
        objects.append(row)
        for key in ('triangles', 'primitives', 'position_vertices'):
            groups[group][key] += row[key]
        groups[group]['nodes'] += 1
    lo = [min(o['bounds_min'][i] for o in objects) for i in range(3)]
    hi = [max(o['bounds_max'][i] for o in objects) for i in range(3)]
    attributes = Counter()
    for mesh in doc['meshes']:
        for p in mesh['primitives']:
            attributes.update(p['attributes'].keys())
    material_signatures = Counter(json.dumps({k: v for k, v in mat.items() if k not in ('name','extras')}, sort_keys=True)
                                  for mat in doc['materials'])
    accessors_bytes = 0
    sizes = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
    component_sizes = {5120:1,5121:1,5122:2,5123:2,5125:4,5126:4}
    for accessor in doc['accessors']:
        accessors_bytes += accessor['count'] * sizes[accessor['type']] * component_sizes[accessor['componentType']]
    return dict(file=path.name, bytes=len(raw), mib=round(len(raw)/1048576, 3),
                triangles=sum(o['triangles'] for o in objects), primitive_draw_calls=sum(o['primitives'] for o in objects),
                position_vertices=sum(o['position_vertices'] for o in objects), nodes=len(doc['nodes']), meshes=len(doc['meshes']),
                materials=len(doc['materials']), unique_material_values=len(material_signatures),
                duplicate_value_materials=sum(c-1 for c in material_signatures.values()),
                textures=len(doc.get('textures', [])), images=len(doc.get('images', [])), texture_resolutions=[],
                attributes=dict(attributes), extensions_used=doc.get('extensionsUsed', []),
                instance_extension_present='EXT_mesh_gpu_instancing' in doc.get('extensionsUsed', []),
                bounds_min=lo, bounds_max=hi, dimensions_m=[hi[i]-lo[i] for i in range(3)],
                decoded_accessor_bytes=accessors_bytes, groups=dict(groups),
                largest_objects=sorted(objects, key=lambda o:o['triangles'], reverse=True)[:20])


if __name__ == '__main__':
    files = [inspect(MODEL / file) for file in ('terrain.glb', 'campus.glb')]
    report = dict(files=files, total_bytes=sum(f['bytes'] for f in files), total_triangles=sum(f['triangles'] for f in files),
                  primitive_draw_calls=sum(f['primitive_draw_calls'] for f in files),
                  decoded_accessor_bytes=sum(f['decoded_accessor_bytes'] for f in files),
                  note='Draw calls are total primitive submissions for a complete single color pass, before view culling, shadows, and post-processing. GPU byte estimate counts decoded accessors, excluding driver padding, render targets and CPU copies.')
    (OUT / 'asset_audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
