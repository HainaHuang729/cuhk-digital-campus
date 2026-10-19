"""Render the independently audited graded-road campus."""
import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_roads_graded.blend'))
scene=bpy.context.scene
next(o for o in bpy.data.objects if 'horizontal_crs' in o).name='CUHK | 1 m graded display terrain | HK1980 grid'
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
scene.cycles.device='GPU';scene.cycles.samples=96;scene.cycles.use_denoising=True
label=bpy.data.collections['10 Building labels / OSM names'];label.hide_render=True
scene.render.filepath=str(ROOT/'CUHK_roads_graded_preview.png');bpy.ops.render.render(write_still=True)
label.hide_render=False;scene.render.filepath=str(ROOT/'CUHK_roads_graded_labeled.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_roads_graded.blend'))
print('GRADED_RENDERS_COMPLETE',flush=True)
