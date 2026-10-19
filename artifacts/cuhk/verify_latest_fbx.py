"""Read every final FBX binary and check its manifest counts and material slots."""
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_ue5 import inspect_fbx
from io_scene_fbx import parse_fbx

folder = ROOT / 'ue5' / 'latest'
manifest = json.loads((folder / 'import_manifest.json').read_text(encoding='utf-8'))
report = json.loads((folder / 'export_report.json').read_text(encoding='utf-8'))
checks = []
material_names = set()
axis = {}
first = {}
for i, batch in enumerate(report['batches']):
    path = folder / batch['file']
    parsed = inspect_fbx(path)
    assert parsed['mesh_count'] == batch['objects'], batch['name']
    assert parsed['vertices'] == batch['vertices'], batch['name']
    assert parsed['triangles'] == batch['triangles'], batch['name']
    root, _ = parse_fbx.parse(str(path))
    stack = [root]
    while stack:
        node = stack.pop()
        stack.extend(node.elems)
        if node.id == b'Material':
            material_names.add(node.props[1].split(b'\x00')[0].decode('utf-8'))
        if i == 0:
            if node.id == b'P' and node.props and node.props[0] in [b'UpAxis', b'UpAxisSign', b'FrontAxis', b'FrontAxisSign', b'CoordAxis', b'CoordAxisSign', b'UnitScaleFactor']:
                axis[node.props[0].decode()] = node.props[-1]
            if node.id == b'Model':
                first['model_name'] = node.props[1].decode('utf-8', errors='replace')
                for child in node.elems:
                    if child.id == b'Properties70':
                        first['model_transform'] = {p.props[0].decode(): list(p.props[4:]) for p in child.elems if p.id == b'P' and p.props[0] in [b'Lcl Translation', b'Lcl Rotation', b'Lcl Scaling']}
            if node.id == b'Vertices':
                vertices = np.asarray(node.props[0]).reshape(-1, 3)
                first['stored_geometry_bounds'] = {'min': vertices.min(axis=0).tolist(), 'max': vertices.max(axis=0).tolist()}
    checks.append({'name': batch['name'], **parsed})
assert material_names == set(manifest['materials']), sorted(material_names ^ set(manifest['materials']))
result = {'all_fbx_counts_match': True, 'files': len(checks), 'material_slots_match_manifest': True,
          'material_count': len(material_names), 'global_axis_settings': axis, 'first_tile': first,
          'batches': checks}
(folder / 'fbx_binary_validation.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in result.items() if k != 'batches'}, ensure_ascii=False), flush=True)
