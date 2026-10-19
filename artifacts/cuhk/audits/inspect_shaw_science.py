import bpy, json
from pathlib import Path
import numpy as np
root = Path(__file__).resolve().parents[1]
bpy.ops.wm.open_mainfile(filepath=str(root / 'CUHK_sports_leveled.blend'))
rows = []
for ob in bpy.data.objects:
    if str(ob.get('osm_id', '')) != '107139044':
        continue
    row = {'name': ob.name, 'type': ob.type, 'hidden': ob.hide_render,
           'collections': [c.name for c in ob.users_collection],
           'properties': {k: str(v) for k, v in ob.items()}, 'location': list(ob.location)}
    if ob.type == 'MESH':
        p = np.array([ob.matrix_world @ v.co for v in ob.data.vertices])
        row.update(bounds=[p.min(0).tolist(), p.max(0).tolist()], vertices=len(p),
                   materials=[m.name for m in ob.data.materials],
                   z_values=np.unique(np.round(p[:, 2], 3)).tolist())
    rows.append(row)
(root / 'audits/shaw_science_before.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps(rows, ensure_ascii=True))
