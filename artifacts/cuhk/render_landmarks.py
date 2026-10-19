"""Render six photo landmark QA views; accepts --source, --width, --samples."""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--source',default=str(root/'CUHK_photo_draft.blend'))
parser.add_argument('--width',type=int,default=1280)
parser.add_argument('--samples',type=int,default=32)
parser.add_argument('--only',default='')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
bpy.ops.wm.open_mainfile(filepath=args.source)
scene=bpy.context.scene
for ob in bpy.data.objects:
    if ob.type=='LIGHT':
        ob.hide_render=False
        ob.hide_set(False)
        for collection in ob.users_collection:
            collection.hide_render=False
        if ob.data.type=='SUN':
            ob.data.energy=2.6
            ob.data.angle=math.radians(8)
    if ob.type=='FONT' or ob.get('label_for') or 'label' in ob.name.lower():
        ob.hide_render=True
scene.render.engine='CYCLES'
scene.cycles.samples=args.samples
scene.cycles.use_adaptive_sampling=True
scene.cycles.adaptive_threshold=.04
scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX'
    prefs.get_devices()
    if any(d.type=='OPTIX' for d in prefs.devices):
        for d in prefs.devices:d.use=d.type=='OPTIX'
        scene.cycles.device='GPU'
except Exception as exc:print('GPU fallback:',exc,flush=True)
scene.render.resolution_x=args.width
scene.render.resolution_y=round(args.width*.75)
scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'
scene.render.image_settings.color_depth='8'
scene.view_settings.view_transform='AgX'
scene.view_settings.exposure=.15
camera_data=bpy.data.cameras.new('Landmark QA camera')
camera=bpy.data.objects.new('Landmark QA camera',camera_data)
scene.collection.objects.link(camera)
scene.camera=camera
camera_data.type='ORTHO'
camera_data.clip_end=10000
camera_data.dof.use_dof=False
output=root/'landmark_previews'
output.mkdir(exist_ok=True)
views={
    '134410449':('library',(1,-.30,.33)),
    '107139030':('shaw_hall',(.30,-1,.40)),
    '134410450':('science',(-1,.04,.25)),
    '201907977':('architecture',(.78,-.75,.34)),
    '201907981':('yasumoto',(-.92,-.38,.32)),
    '1424900701':('lo_kwee_seong',(-.67,-1,.32)),
}
for osm_id,(name,direction) in views.items():
    if args.only and name not in args.only.split(','):continue
    ob=next(o for o in bpy.data.objects if o.get('landmark_rebuilt') and str(o.get('osm_id'))==osm_id)
    points=[ob.matrix_world@Vector(v) for v in ob.bound_box]
    target=sum(points,Vector())/8
    dimension=Vector([max(p[i] for p in points)-min(p[i] for p in points) for i in range(3)])
    # Pixel frame encompasses the entire main mass with enough foreground to inspect supports.
    scale=max(dimension.x,dimension.y,dimension.z)*1.45
    camera.location=target+Vector(direction).normalized()*scale*2.5
    camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
    camera_data.ortho_scale=scale
    scene.render.filepath=str(output/(name+'.png'))
    bpy.ops.render.render(write_still=True)
    print('LANDMARK_RENDERED',osm_id,name,flush=True)
print('LANDMARKS_COMPLETE',flush=True)
