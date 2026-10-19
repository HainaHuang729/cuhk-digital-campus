"""Render all campus names without changing the saved default camera."""
import bpy,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
bpy.ops.wm.open_mainfile(filepath=str(root/'CUHK_photo_rebuilt.blend'))
scene=bpy.context.scene;scene.camera=bpy.data.objects['Camera / north-up plan'];scene.camera.data.ortho_scale=2900
scene.render.resolution_x=4000;scene.render.resolution_y=4400;scene.render.resolution_percentage=100
scene.cycles.samples=96;scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
scene.cycles.device='GPU'
from building_labels import apply_building_labels
bpy.context.view_layer.update();stats=apply_building_labels(scene.camera,'plan')
(root/'photo_plan_label_stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
scene.render.filepath=str(root/'CUHK_photo_rebuilt_plan.png');bpy.ops.render.render(write_still=True)
print('PHOTO_PLAN_COMPLETE',flush=True)
