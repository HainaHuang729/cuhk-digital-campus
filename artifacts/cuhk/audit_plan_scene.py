import bpy, json, sys
from pathlib import Path
from mathutils import Vector
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_ue5 import selected_geometry
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'CUHK_shaw_science_corrected.blend'))
groups = {}
for group, obj in selected_geometry(bpy.context.scene):
    d = groups.setdefault(group, {'count': 0, 'materials': set(), 'bounds': [[1e9]*3, [-1e9]*3], 'examples': []})
    d['count'] += 1
    d['materials'].update(m.name for m in obj.data.materials if m)
    if len(d['examples']) < 8: d['examples'].append(obj.name)
    for corner in obj.bound_box:
        p = obj.matrix_world @ Vector(corner)
        for i in range(3):
            d['bounds'][0][i] = min(d['bounds'][0][i], p[i])
            d['bounds'][1][i] = max(d['bounds'][1][i], p[i])
for d in groups.values(): d['materials'] = sorted(d['materials'])
output = {'collections': [{'name': c.name, 'hide_render': c.hide_render, 'count': len(c.objects)} for c in bpy.data.collections], 'groups': groups}
(ROOT / 'plan_scene_audit.json').write_text(json.dumps(output, indent=2), encoding='utf-8')
print('AUDIT_COMPLETE', len(bpy.data.objects))
