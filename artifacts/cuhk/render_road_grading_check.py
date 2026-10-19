"""Identical-view Blender geometry checks of the connected and graded road models.

blender --background --python render_road_grading_check.py -- --only before --preview
blender --background --python render_road_grading_check.py -- --only after
Never saves either source .blend file.
"""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--preview', action='store_true')
parser.add_argument('--only', choices=['before', 'after'])
parser.add_argument('--view', choices=['bridgehead', 'hostel'])
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
views = {
    'bridgehead': dict(target=(305.427638651, 205.126932662, 138), offset=(-10, 75, 58), scale=78),
    'hostel': dict(target=(-263, 244, 139), offset=(-100, -25, 72), scale=105),
}

for suffix, source in [('before', 'CUHK_connected_roads.blend'), ('after', 'CUHK_roads_graded.blend')]:
    if args.only and suffix != args.only:
        continue
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/source))
    scene = bpy.context.scene
    for collection in bpy.data.collections:
        if collection.name.startswith(('09 ', '10 ')):
            collection.hide_render = True
    for obj in bpy.data.objects:
        if obj.type == 'FONT' or obj.type == 'LIGHT' or obj.get('label_for'):
            obj.hide_render = True

    def material(name, color):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        bs = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        bs.inputs['Base Color'].default_value = (*color, 1)
        bs.inputs['Roughness'].default_value = .82
        out = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
        return mat

    highlight = material('Grading check / amber selected roads', (.56, .24, .055))
    asphalt = material('Grading check / uniform asphalt', (.105, .125, .128))
    footpath = material('Grading check / uniform path', (.42, .405, .325))
    for obj in bpy.data.collections['04 Roads and paths'].objects:
        if obj.type != 'MESH':
            continue
        if str(obj.get('osm_id', '')) in ('213510397', '213510536'):
            mat = highlight
        else:
            old_names = ' '.join(m.name.lower() for m in obj.data.materials if m)
            mat = footpath if any(word in old_names for word in ('foot', 'path', 'step')) else asphalt
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    sun_data = bpy.data.lights.new('Grading check / identical Sun', type='SUN')
    sun_data.energy = 2.2
    sun_data.angle = math.radians(12)
    sun_data.color = (1, .95, .88)
    sun = bpy.data.objects.new('Grading check / identical Sun', sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (.35, -.45, -.45)
    scene.world.use_nodes = True
    nodes = scene.world.node_tree.nodes
    background = next((n for n in nodes if n.type == 'BACKGROUND'), None)
    if background is None:
        background = nodes.new('ShaderNodeBackground')
        out = nodes.new('ShaderNodeOutputWorld')
        scene.world.node_tree.links.new(background.outputs['Background'], out.inputs['Surface'])
    background.inputs['Color'].default_value = (.55, .62, .68, 1)
    background.inputs['Strength'].default_value = .65
    camera_data = bpy.data.cameras.new('Grading check / fixed camera')
    camera = bpy.data.objects.new('Grading check / fixed camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = 'ORTHO'
    camera_data.clip_start = .05
    camera_data.clip_end = 10000
    camera_data.dof.use_dof = False
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 12 if args.preview else 32
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .04
    prefs = bpy.context.preferences.addons['cycles'].preferences
    try:
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        if any(d.type == 'OPTIX' for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == 'OPTIX'
            scene.cycles.device = 'GPU'
    except Exception as exc:
        print('GPU fallback:', exc, flush=True)
    scene.render.resolution_x = 960 if args.preview else 1600
    scene.render.resolution_y = 720 if args.preview else 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = .05
    scene.render.film_transparent = False
    for view, setting in views.items():
        if args.view and args.view != view:
            continue
        target = Vector(setting['target'])
        camera.location = target+Vector(setting['offset'])
        camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
        camera_data.ortho_scale = setting['scale']
        filename = f'road_grading_{view}_{suffix}{"_preview" if args.preview else ""}.png'
        scene.render.filepath = str(ROOT/filename)
        bpy.ops.render.render(write_still=True)
        print('GRADING_CHECK_RENDERED', suffix, view, json.dumps(setting), flush=True)
print('GRADING_CHECK_COMPLETE', flush=True)
