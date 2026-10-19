"""Refresh material metadata from the source Blend without re-exporting geometry."""
import json
import sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_ue5 import simple_material

path = ROOT / 'ue5/latest/import_manifest.json'
manifest = json.loads(path.read_text(encoding='utf-8'))
source = Path(manifest['source_scene'])
before = source.stat()
bpy.ops.wm.open_mainfile(filepath=str(source))
count = 0
for values in manifest['materials'].values():
    name = values['original_name']
    material = bpy.data.materials.get(name)
    if material is None and name != 'Unassigned neutral surface':
        raise RuntimeError(f'Missing source material: {name}')
    sided = not material.use_backface_culling if material else True
    count += values.get('two_sided') != sided
    values['two_sided'] = sided

# The exporter must preserve both explicit source choices and its neutral default.
probe = bpy.data.materials.new('Sidedness diagnostic only')
for source_culls in (False, True):
    probe.use_backface_culling = source_culls
    palette = {}
    generated = simple_material(probe, palette, {})
    assert palette[generated.name]['two_sided'] == (not source_culls)
    assert generated.use_backface_culling == source_culls
palette = {}
generated = simple_material(None, palette, {})
assert palette[generated.name]['two_sided'] is True

manifest['material_sidedness_note'] = 'Preserves inverse source Blender use_backface_culling. Mixed face directions require double-sided materials; current UE master is double-sided.'
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
temporary.replace(path)
after = source.stat()
assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
print(json.dumps({'material_count': len(manifest['materials']), 'metadata_changed': count,
                  'two_sided_materials': sum(v['two_sided'] for v in manifest['materials'].values()),
                  'source_blend_unchanged': True, 'exporter_sidedness_checks_passed': True}), flush=True)
