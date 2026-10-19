"""Read source collection, linked mesh and prop structure; never save blend."""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from export_ue5 import selected_geometry
SOURCE = ROOT / 'CUHK_shaw_science_corrected.blend'
stamp = (SOURCE.stat().st_mtime_ns, SOURCE.stat().st_size)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
groups = defaultdict(list)
for group, obj in selected_geometry(bpy.context.scene):
    groups[group].append(obj)
trees = groups['09']
templates = Counter(obj.data.name for obj in trees)
props = []
for obj in groups['08']:
    obj.data.calc_loop_triangles()
    props.append(dict(name=obj.name, triangles=len(obj.data.loop_triangles),
                      materials=[m.name for m in obj.data.materials], properties=dict(obj.items())))
result = dict(source=str(SOURCE), source_unchanged=True,
              collection_groups={g:dict(objects=len(obs), types=dict(Counter(o.type for o in obs)),
                                        distinct_meshes=len({o.data.name for o in obs})) for g,obs in groups.items()},
              vegetation=dict(objects=len(trees), shared_mesh_counts=dict(templates),
                              sample=dict(name=trees[0].name, position=list(trees[0].location),
                                          scale=list(trees[0].scale), properties=dict(trees[0].items())),
                              mesh_topologies={name:dict(vertices=len(bpy.data.meshes[name].vertices),
                                                        polygons=len(bpy.data.meshes[name].polygons)) for name in templates}),
              props=props,
              images=[dict(name=i.name, size=list(i.size), filepath=i.filepath) for i in bpy.data.images],
              scene_site_properties={k:v for k,v in bpy.context.scene.items() if 'detail' in k.lower() or 'refine' in k.lower()})
assert stamp == (SOURCE.stat().st_mtime_ns, SOURCE.stat().st_size)
out = Path(__file__).resolve().parent / 'blender_structure_audit.json'
out.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print('BLENDER_AUDIT', json.dumps(result, ensure_ascii=False, default=str))
