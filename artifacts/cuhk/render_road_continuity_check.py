"""Actual Blender geometry inspection renders; never saves either source blend.

Blender --background --python render_road_continuity_check.py -- --preview
Blender --background --python render_road_continuity_check.py
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
parser.add_argument('--only', choices=['before', 'after'], default=None)
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])

# Same metric camera, Sun and world in both scenes. The 13.39 m centerline height
# mismatch was measured at the genuine OSM transition node, not at a made-up join.
target = Vector((305.427638651, 205.126932662, 138.0))
offset = Vector((-10.0, 75.0, 58.0))
scale = 78.0
for suffix, source in [('before', 'CUHK_photo_rebuilt.blend'), ('after', 'CUHK_connected_roads.blend')]:
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
    # An identical amber inspection material marks only the two source roads;
    # it does not alter their meshes or reveal geometry through the terrain.
    highlight = bpy.data.materials.new('Road check / highlighted source roads')
    highlight.use_nodes = True
    nodes = highlight.node_tree.nodes
    nodes.clear()
    bs = nodes.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (.56, .24, .055, 1)
    bs.inputs['Roughness'].default_value = .82
    out = nodes.new('ShaderNodeOutputMaterial')
    highlight.node_tree.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    for obj in bpy.data.collections['04 Roads and paths'].objects:
        if str(obj.get('osm_id', '')) in ('213510397', '213510536'):
            obj.data.materials.clear()
            obj.data.materials.append(highlight)
    sun_data = bpy.data.lights.new('Road check / identical Sun', type='SUN')
    sun_data.energy = 2.2
    sun_data.angle = math.radians(12)
    sun_data.color = (1.0, .95, .88)
    sun = bpy.data.objects.new('Road check / identical Sun', sun_data)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (.35, -.45, -.45)
    scene.world.use_nodes = True
    world = scene.world.node_tree.nodes
    background = next((n for n in world if n.type == 'BACKGROUND'), None)
    if background is None:
        background = world.new('ShaderNodeBackground')
        out = world.new('ShaderNodeOutputWorld')
        scene.world.node_tree.links.new(background.outputs['Background'], out.inputs['Surface'])
    background.inputs['Color'].default_value = (.55, .62, .68, 1)
    background.inputs['Strength'].default_value = .65

    camera_data = bpy.data.cameras.new('Road check / identical camera')
    camera = bpy.data.objects.new('Road check / identical camera', camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera.location = target+offset
    camera.rotation_euler = (target-camera.location).to_track_quat('-Z', 'Y').to_euler()
    camera_data.type = 'ORTHO'
    camera_data.ortho_scale = scale
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
    scene.render.filepath = str(ROOT/f'road_continuity_{suffix}{"_preview" if args.preview else ""}.png')
    bpy.ops.render.render(write_still=True)
    print('ROAD_CHECK_RENDERED', suffix, flush=True)

print('ROAD_CHECK_COMPLETE', json.dumps(dict(target=list(target), camera=list(target+offset), orthographic_scale=scale)), flush=True)
