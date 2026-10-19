"""Render the existing geographic model at high resolution without rebuilding it."""
import bpy
from pathlib import Path
root=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(root/'CUHK_terrain_buildings.blend'))
scene=bpy.context.scene
scene.camera=bpy.data.objects['Camera / southeast overview']
scene.render.engine='CYCLES'
scene.cycles.samples=160
scene.cycles.use_adaptive_sampling=True
scene.cycles.adaptive_threshold=.015
scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    gpu=[d for d in prefs.devices if d.type=='OPTIX']
    if gpu:
        for d in prefs.devices: d.use=d.type=='OPTIX'
        scene.cycles.device='GPU'
        print('Render device:',[d.name for d in gpu],flush=True)
except Exception as exc:
    print('Using CPU:',exc,flush=True)
scene.render.resolution_x=3200
scene.render.resolution_y=2800
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.render.image_settings.color_depth='8'
scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=.35
scene.render.filepath=str(root/'CUHK_render_3200.png')
bpy.ops.render.render(write_still=True)
print('RENDER_COMPLETE',scene.render.filepath,flush=True)
