"""Render both stadiums from fixed cameras, then the revised campus overview."""
import bpy,json,sys
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
before='--before' in sys.argv
source='CUHK_roads_graded.blend' if before else 'CUHK_sports_leveled.blend'
bpy.ops.wm.open_mainfile(filepath=str(ROOT/source))
scene=bpy.context.scene;original_camera=scene.camera
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
scene.render.engine='CYCLES';scene.cycles.device='GPU'
scene.cycles.samples=48;scene.cycles.use_denoising=True
scene.render.image_settings.file_format='PNG'
label=bpy.data.collections['10 Building labels / OSM names'];label.hide_render=True
camera_data=bpy.data.cameras.new('Stadium check camera')
camera=bpy.data.objects.new('Stadium check camera',camera_data);scene.collection.objects.link(camera)
camera_data.type='ORTHO';camera_data.clip_end=10000
scene.camera=camera;scene.render.resolution_x=2000;scene.render.resolution_y=1600;scene.render.resolution_percentage=100
facilities=json.loads((ROOT/'sports_platforms.json').read_text('utf-8'))['facilities']
for f in facilities:
    target=Vector((*f['center_xy'],f['surface_z_m']))
    camera.location=target+Vector((185,-170,250));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.ortho_scale=280 if str(f['track_id'])=='955764574' else 245
    scene.render.filepath=str(ROOT/f'stadium_{f["track_id"]}_{"before" if before else "after"}.png')
    bpy.ops.render.render(write_still=True)
scene.camera=original_camera;bpy.data.objects.remove(camera,do_unlink=True)
if not before:
    scene.render.resolution_x=3600;scene.render.resolution_y=2700;scene.cycles.samples=96
    scene.render.filepath=str(ROOT/'CUHK_sports_leveled_preview.png');bpy.ops.render.render(write_still=True)
    label.hide_render=False
    scene.render.filepath=str(ROOT/'CUHK_sports_leveled_labeled.png');bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/source))
print('SPORTS_RENDERS_COMPLETE',flush=True)
