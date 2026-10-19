"""Render style studies from the existing campus. Never saves/edits the source blend.

blender --background --python render_plan_styles.py -- --size 3000 --samples 64
"""
import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_ue5 import selected_geometry

parser = argparse.ArgumentParser()
parser.add_argument('--size', type=int, default=3000)
parser.add_argument('--samples', type=int, default=64)
parser.add_argument('--styles', default='ABCD')
parser.add_argument('--navigation', action='store_true', help='Flat road-first navigation map studies')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
if args.navigation:
    args.styles = 'EF' if args.styles == 'ABCD' else args.styles
    if any(style not in 'EFGHIJ' for style in args.styles):
        parser.error('Navigation styles must be selected from EFGHIJ')
OUT = ROOT / ('navigation_styles_20261004' if args.navigation else 'plan_styles_20261004')
OUT.mkdir(exist_ok=True)
SOURCE = ROOT / 'CUHK_shaw_science_corrected.blend'
source_stat = (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns)

# sRGB art-direction colors. Only shading and lighting change between versions.
PALETTES = {
    'A': dict(title='自然导览', ground='9FB38F', high='BDC7A4', wall='E5DBC4', roof='F3EBDD', accent='C5B38D', glass='698891', road='758377', path='DED5BD', water='68A6B0', pitch='82A567', track='C18568', tree='3D6447', tree2='6B814D', context='B7BFAB', detail='A7B7AC', ink='F6F1DC'),
    'B': dict(title='纯白沙盘', ground='D5D1C9', high='E4E0D8', wall='EEEAE2', roof='FCF8EF', accent='D5CEC2', glass='C8C8C4', road='BAB7B0', path='ECE6DB', water='BDC9CC', pitch='CECEBF', track='B9B8AF', tree='D8D6CB', tree2='E5E1D6', context='DAD7D0', detail='CCC9C3', ink='F8F5ED'),
    'C': dict(title='珊瑚薄荷', ground='C9DDC5', high='E4EACA', wall='EDC6AC', roof='DF9B82', accent='CD997A', glass='699AA7', road='B8B19A', path='F5E9C9', water='89BDC9', pitch='A2C793', track='C395A3', tree='73A88D', tree2='9DC2A0', context='D4CFB6', detail='DDC19B', ink='FFF4D8'),
    'D': dict(title='深蓝图谱', ground='183446', high='29495C', wall='587C90', roof='B6D9DF', accent='7BA7B4', glass='345C71', road='829CA7', path='AEBAA3', water='112D40', pitch='305866', track='BC9570', tree='315D6B', tree2='4F7780', context='426477', detail='688D9E', ink='CBE2DC'),
    'E': dict(title='浅绿导航', ground='EBF0E4', high='EBF0E4', wall='D0D7D0', roof='D0D7D0', accent='D0D7D0', glass='D0D7D0', road='FFFDF7', path='F4E3BE', water='BCDDE2', pitch='D0DFC6', track='DED4C4', tree='DBE6D2', tree2='DBE6D2', context='DDE2D9', detail='D0D7D0', ink='EEF2E9', road_edge='89958A', path_edge='A29575', context_road='E0E4DB', context_edge='C6CDC1'),
    'F': dict(title='蓝灰路网', ground='F3F5F5', high='F3F5F5', wall='E0E5E7', roof='E0E5E7', accent='E0E5E7', glass='E0E5E7', road='8DA3AF', path='B4C6C7', water='C2E0E9', pitch='E3EBDE', track='E6E1D7', tree='E7EDE5', tree2='E7EDE5', context='E9EDEF', detail='E0E5E7', ink='F5F7F5', road_edge='718A99', path_edge='86A5A9', context_road='DFE5E8', context_edge='CDD6DB'),
}
PALETTES.update({
    'G': PALETTES['E'] | dict(title='暖米地图', ground='F5F0E6', high='F5F0E6', wall='DFD9CE', roof='DFD9CE', accent='DFD9CE', glass='DFD9CE', detail='DFD9CE', context='E8E2D8', road='FFFEFA', road_edge='A09382', path='E8C7A3', path_edge='B59D7D', water='BADBE1', pitch='DCE3CD', track='E3D7C4', context_road='E7E0D5', context_edge='D4CCBF'),
    'H': PALETTES['F'] | dict(title='薄荷步行', ground='F0F5EF', high='F0F5EF', wall='DDE6DE', roof='DDE6DE', accent='DDE6DE', glass='DDE6DE', detail='DDE6DE', context='E5ECE5', road='749589', road_edge='5E7D74', path='A6C7B1', path_edge='79A78E', water='B8DEE3', pitch='D6E5CD', track='DDE1D0', context_road='DEE7DF', context_edge='C8D5CB'),
    'I': PALETTES['F'] | dict(title='清晰灰白', ground='FAFBFC', high='FAFBFC', wall='E4E8EB', roof='E4E8EB', accent='E4E8EB', glass='E4E8EB', detail='E4E8EB', context='EEF0F2', road='596873', road_edge='4E5D69', path='A7B4BC', path_edge='8397A4', water='C8E3ED', pitch='E3E9DF', track='E7E3DA', context_road='E3E8EB', context_edge='D2D9DE'),
    'J': PALETTES['F'] | dict(title='夜间导航', ground='192B36', high='192B36', wall='304552', roof='304552', accent='304552', glass='304552', detail='304552', context='253A47', road='91ACBC', road_edge='6C899C', path='527B85', path_edge='436470', water='143F51', pitch='294938', track='4D4D41', context_road='2C4352', context_edge='344E5F'),
})

def rgb(code):
    channels = [int(code[i:i+2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + .055) / 1.055) ** 2.4 for c in channels)

def category(name, group):
    n = name.lower()
    if group == '01': return 'ground' if 'ground' in n else 'context'
    if group == '03': return 'context'
    if group == '04': return 'road' if 'asphalt' in n else 'path'
    if group == '14': return 'path'
    if 'canopy' in n: return 'tree2' if any(str(i) in n for i in (1, 3, 5)) else 'tree'
    if 'bark' in n: return 'accent'
    if 'water' in n: return 'water'
    if 'pitch' in n or 'turf' in n: return 'pitch'
    if 'track' in n: return 'track'
    if 'paint' in n or 'rope' in n or 'goal' in n: return 'ink'
    if 'curb' in n: return 'path'
    if any(k in n for k in ('glaz', 'glass', 'steel', 'charcoal')): return 'glass'
    if any(k in n for k in ('roof', 'terracotta')): return 'roof'
    if any(k in n for k in ('accent', 'fin', 'metal', 'louvre', 'aluminium', 'aluminum')): return 'accent'
    if any(k in n for k in ('wall', 'facade', 'concrete', 'white', 'trim', 'frame')): return 'wall'
    return 'detail'

def make_material(key, palette, style):
    m = bpy.data.materials.new('Plan study ' + style + ' / ' + key)
    m.diffuse_color = (*rgb(palette[key]), 1)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    if args.navigation:
        emission = nt.nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (*rgb(palette[key]), 1)
        nt.links.new(emission.outputs[0], out.inputs['Surface'])
        return m
    bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bs.inputs['Base Color'].default_value = (*rgb(palette[key]), 1)
    bs.inputs['Roughness'].default_value = 1.0
    bs.inputs['Specular IOR Level'].default_value = .1
    nt.links.new(bs.outputs['BSDF'], out.inputs['Surface'])
    if key == 'ground':
        geometry = nt.nodes.new('ShaderNodeNewGeometry')
        xyz = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(geometry.outputs['Position'], xyz.inputs[0])
        normalize = nt.nodes.new('ShaderNodeMapRange')
        normalize.inputs['From Min'].default_value = 0
        normalize.inputs['From Max'].default_value = 260
        nt.links.new(xyz.outputs['Z'], normalize.inputs['Value'])
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].color = (*rgb(palette['ground']), 1)
        ramp.color_ramp.elements[1].color = (*rgb(palette['high']), 1)
        nt.links.new(normalize.outputs[0], ramp.inputs[0])
        color = ramp.outputs[0]
        if style == 'D':
            spacing = nt.nodes.new('ShaderNodeMath'); spacing.operation = 'MULTIPLY'
            spacing.inputs[1].default_value = .1
            nt.links.new(xyz.outputs['Z'], spacing.inputs[0])
            frac = nt.nodes.new('ShaderNodeMath'); frac.operation = 'FRACT'
            nt.links.new(spacing.outputs[0], frac.inputs[0])
            line = nt.nodes.new('ShaderNodeMath'); line.operation = 'LESS_THAN'
            line.inputs[1].default_value = .045
            nt.links.new(frac.outputs[0], line.inputs[0])
            blend = nt.nodes.new('ShaderNodeMixRGB')
            nt.links.new(line.outputs[0], blend.inputs[0])
            nt.links.new(color, blend.inputs[1])
            blend.inputs[2].default_value = (*rgb('3A5D70'), 1)
            color = blend.outputs[0]
        nt.links.new(color, bs.inputs['Base Color'])
    return m

bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene
renderables = selected_geometry(scene)
if args.navigation:
    # Same authored geometry, no canopy clutter, 3D shadows, labels or road slabs.
    renderables = [(group, obj) for group, obj in renderables if group in {'01', '02', '03', '05', '11'}]
allowed = {obj.name for _, obj in renderables}
for obj in scene.objects:
    if obj.type in {'MESH', 'CURVE', 'FONT', 'SURFACE', 'META', 'LIGHT'}:
        obj.hide_render = obj.name not in allowed
original_slots = [(group, obj, [m.name if m else '' for m in obj.data.materials]) for group, obj in renderables]

road_symbols = []
road_counts = {}
if args.navigation:
    network = json.loads((ROOT / 'road_network_v3.json').read_text(encoding='utf-8'))
    profiles = [p for p in network['profiles'] if p['surface_class'] in {'ground', 'elevated'} and len(p['points']) > 1]
    for profile in profiles:
        kind = profile['highway']
        is_context = not profile['campus'] or kind in {'motorway', 'motorway_link', 'trunk', 'trunk_link'}
        walking = kind in {'footway', 'path', 'steps', 'pedestrian', 'cycleway', 'bridleway'}
        road_type = 'context' if is_context else ('walk' if walking else 'street')
        road_counts[road_type] = road_counts.get(road_type, 0) + 1
        width = max(3, min(float(profile['width']), 8)) if is_context else (4.5 if walking else max(7, min(float(profile['width']), 12)))
        core_key, edge_key, level = {'context': ('context_road', 'context_edge', 800), 'street': ('road', 'road_edge', 900), 'walk': ('path', 'path_edge', 1000)}[road_type]
        # Keep the inner stroke above the outer tube's full radius in an orthographic view.
        for key, stroke_width, z in ((edge_key, width + (1.0 if is_context else 2.0), level), (core_key, width, level + 20)):
            curve = bpy.data.curves.new(f"Map road {profile['id']}/{profile['part']} {key}", 'CURVE')
            curve.dimensions = '3D'
            curve.resolution_u = 1
            curve.bevel_depth = stroke_width / 2
            curve.bevel_resolution = 1
            curve.use_fill_caps = True
            spline = curve.splines.new('POLY')
            spline.points.add(len(profile['points']) - 1)
            for vertex, point in zip(spline.points, profile['points']):
                vertex.co = (point[0], point[1], z, 1)
            obj = bpy.data.objects.new(curve.name, curve)
            scene.collection.objects.link(obj)
            road_symbols.append((obj, key))
    print('MAP_ROADS', road_counts, flush=True)

cam_data = bpy.data.cameras.new('Plan studies / true north-up')
cam = bpy.data.objects.new('Plan studies / true north-up', cam_data)
scene.collection.objects.link(cam)
cam.location = (40, 0, 5000)
cam.rotation_euler = (0, 0, 0)
cam.data.type = 'ORTHO'
cam.data.ortho_scale = 2250
cam.data.clip_end = 10000
scene.camera = cam

sun_data = bpy.data.lights.new('Plan studies / northwest sun', 'SUN')
sun = bpy.data.objects.new('Plan studies / northwest sun', sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = Vector((1300, -1600, -3000)).to_track_quat('-Z', 'Y').to_euler()
sun_data.energy = 2.1
sun_data.angle = math.radians(7)

world = bpy.data.worlds.new('Plan studies / diffuse sky')
world.use_nodes = True
world.node_tree.nodes.clear()
background = world.node_tree.nodes.new('ShaderNodeBackground')
world_output = world.node_tree.nodes.new('ShaderNodeOutputWorld')
world.node_tree.links.new(background.outputs[0], world_output.inputs['Surface'])
background.inputs[0].default_value = (.8, .85, .9, 1)
background.inputs[1].default_value = .6
scene.world = world
scene.render.engine = 'CYCLES'
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.adaptive_threshold = .015
scene.cycles.max_bounces = 4
scene.cycles.diffuse_bounces = 2
scene.cycles.glossy_bounces = 1
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices: device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
    print('RENDER_DEVICES', [(d.name, d.type, d.use) for d in prefs.devices], flush=True)
except Exception as exc:
    print('CPU fallback:', str(exc), flush=True)
    scene.cycles.device = 'CPU'
scene.render.resolution_x = args.size
scene.render.resolution_y = args.size
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '8'
scene.render.film_transparent = False
scene.render.use_compositing = False
scene.render.use_sequencer = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .3
if args.navigation:
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.render.dither_intensity = 0
    scene.display.shading.light = 'FLAT'
    scene.display.shading.color_type = 'MATERIAL'
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = False
    scene.display.shading.show_specular_highlight = False
    scene.display.shading.show_object_outline = False
    scene.view_settings.view_transform = 'Standard'
    scene.view_settings.look = 'None'
    scene.view_settings.exposure = 0
    scene.cycles.use_denoising = False

for style in args.styles:
    palette = PALETTES[style]
    mats = {key: make_material(key, palette, style) for key in palette if key not in {'title', 'high'}}
    for group, obj, names in original_slots:
        for index, name in enumerate(names):
            obj.data.materials[index] = mats[category(name, group)]
    sun_data.angle = math.radians(10 if style == 'B' else 7)
    sun_data.energy = 2.5 if style == 'B' else 2.1
    scene.view_settings.exposure = 0 if args.navigation else (.15 if style == 'D' else .3)
    for obj, key in road_symbols:
        obj.data.materials.clear()
        obj.data.materials.append(mats[key])
    cam.location = (40, 0, 5000)
    cam.data.ortho_scale = 2250
    scene.render.resolution_x = scene.render.resolution_y = args.size
    scene.render.filepath = str(OUT / ('raw_' + style + '.png'))
    print('RENDER_START', style, palette['title'], flush=True)
    bpy.ops.render.render(write_still=True)
    if args.navigation:
        # A second camera view tests the same map at a mobile walking-scale zoom.
        cam.location = (180, -180, 5000)
        cam.data.ortho_scale = 1830
        scene.render.resolution_x = 900
        scene.render.resolution_y = 1650
        scene.render.filepath = str(OUT / ('mobile_' + style + '.png'))
        bpy.ops.render.render(write_still=True)
    print('RENDER_COMPLETE', style, flush=True)

assert source_stat == (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns), 'Source must remain unchanged'
(OUT / ('render-manifest-' + args.styles + '.json' if args.navigation and args.styles != 'EF' else 'render-manifest.json')).write_text(json.dumps({
    'source': str(SOURCE), 'sourceUnchanged': True,
    'createdAt': datetime.now(timezone.utc).isoformat(),
    'camera': {'type': 'orthographic', 'position': [40, 0, 5000], 'rotationRadians': [0, 0, 0], 'viewWidthMetres': 2250, 'north': '+Y / image up'},
    'render': {'engine': scene.render.engine, 'size': args.size, 'samples': args.samples, 'visibleObjects': len(renderables)},
    'styles': {s: PALETTES[s] for s in args.styles},
    'navigation': {'enabled': args.navigation, 'roadSource': 'road_network_v3.json', 'roadCounts': road_counts, 'crs': 'EPSG:2326', 'originHK1980': [839400, 831150], 'squareBoundsLocal': {'xmin': -1085, 'ymin': -1125, 'xmax': 1165, 'ymax': 1125}, 'pixelMapping': 'u=(x+1085)/2250*imageWidth; v=(1125-y)/2250*imageHeight', 'mobileCamera': {'x': 180, 'y': -180, 'heightMetres': 1830, 'widthMetres': 1830*900/1650, 'pixels': [900, 1650]}, 'symbolization': 'Road centers retained; display strokes widened. Ground/elevated shown; indoor/tunnel/below_ground hidden. Highway context muted. No turn-by-turn routing inferred.'},
    'changes': 'Render-only flat materials and road symbols from existing centers. Trees/details hidden for legibility. No source geometry saved or changed.' if args.navigation else 'Render-only materials, lighting and camera. Original geometry, roads and building detail retained. Dense labels hidden. No blend file saved.',
    'note': 'Style studies from existing campus model; not a surveyed or official campus map.'
}, ensure_ascii=False, indent=2), encoding='utf-8')
print('ALL_RENDERS_COMPLETE', flush=True)
