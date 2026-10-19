"""Camera-facing CUHK building labels from original OSM name properties.

Call apply_building_labels(camera, mode='closeup') after camera and output
resolution have been set. Modes closeup, overview and plan share the same
collision-avoiding layout; plan uses slightly larger type. Re-call to change
camera. Each original campus building gets editable text and a name record,
including buildings outside the selected view (hidden in the render).
"""
import json
import math
import unicodedata
from pathlib import Path

import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view


GROUP = '10 Building labels / OSM names'


def _emission(name, color):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    shader = nodes.new('ShaderNodeEmission')
    shader.inputs['Color'].default_value = (*color, 1)
    shader.inputs['Strength'].default_value = 1
    output = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(shader.outputs[0], output.inputs['Surface'])
    mat.diffuse_color = (*color, 1)
    return mat


def _wrap_name(value, max_units=14):
    """Wrap full names without dropping or inventing any characters."""
    lines, current, units = [], '', 0
    for char in value:
        width = 1 if unicodedata.east_asian_width(char) in ('W', 'F') else .55
        if units + width > max_units and current:
            lines.append(current.strip())
            current, units = '', 0
        current += char
        units += width
    if current:
        lines.append(current.strip())
    return '\n'.join(lines)


def _overlap(a, b, padding=8):
    return (abs(a[0] - b[0]) < (a[2] + b[2]) * .5 + padding and
            abs(a[1] - b[1]) < (a[3] + b[3]) * .5 + padding)


def apply_building_labels(camera=None, mode='closeup'):
    scene = bpy.context.scene
    camera = camera or scene.camera or bpy.data.objects.get('Camera / core architectural detail')
    if isinstance(camera, str):
        camera = bpy.data.objects[camera]
    if camera is None or camera.type != 'CAMERA':
        raise ValueError('A scene camera is required for building label placement')
    group = bpy.data.collections.get(GROUP)
    if group is None:
        group = bpy.data.collections.new(GROUP)
        scene.collection.children.link(group)
    for obj in list(group.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)

    font = None
    for file in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf',
                 'C:/Windows/Fonts/simsun.ttc'):
        if Path(file).is_file():
            font = next((f for f in bpy.data.fonts if f.filepath == file), None)
            font = font or bpy.data.fonts.load(file)
            try:
                font.pack()
            except (AttributeError, RuntimeError):
                pass
            break
    if font is None:
        raise RuntimeError('No local Chinese font found; cannot render Chinese labels')

    navy = _emission('Labels / deep navy', (.010, .029, .049))
    white = _emission('Labels / warm white', (.96, .98, 1.0))
    cyan = _emission('Labels / soft cyan', (.22, .63, .73))
    leader_mat = _emission('Labels / fine leaders', (.70, .88, .89))
    dark_leader = _emission('Labels / leader outline', (.011, .038, .045))
    width = scene.render.resolution_x * scene.render.resolution_percentage / 100
    height = scene.render.resolution_y * scene.render.resolution_percentage / 100
    # Type remains readable in each full-resolution export.
    font_px = 25 if mode in ('plan', 'topdown') else 23
    frame = camera.data.view_frame(scene=scene)
    xmin, xmax = min(v.x for v in frame), max(v.x for v in frame)
    ymin, ymax = min(v.y for v in frame), max(v.y for v in frame)
    depth = max(camera.data.clip_start + 5, 30)
    frame_scale = depth / abs(frame[0].z) if camera.data.type != 'ORTHO' else 1
    px_world = (xmax - xmin) * frame_scale / width
    rotation = camera.matrix_world.to_quaternion()

    def point(x, y, z=0):
        return camera.matrix_world @ Vector(((xmin + (xmax - xmin) * x / width) * frame_scale,
                                             (ymin + (ymax - ymin) * y / height) * frame_scale,
                                             -depth + z))

    def configure(obj, record, visible):
        obj.hide_render = not visible
        obj.hide_viewport = not visible
        obj['building_osm_id'] = record['osm_id']
        obj['building_name'] = record['name']
        obj['name_source'] = record['name_source']
        obj['annotation_camera'] = camera.name
        obj['annotation_mode'] = mode
        obj['roof_anchor_world'] = record['anchor_world']
        for key in ('visible_shadow', 'visible_diffuse', 'visible_glossy',
                    'visible_transmission', 'visible_volume_scatter'):
            if hasattr(obj, key):
                setattr(obj, key, False)

    def polygon(name, coordinates, material, record, visible, z=0):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([point(x, y, z) for x, y in coordinates], [],
                         [tuple(range(len(coordinates)))])
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name, mesh)
        group.objects.link(obj)
        configure(obj, record, visible)
        return obj

    def rounded(name, box, material, record, visible):
        x, y, w, h = box
        r = min(6, h * .2)
        coordinates = []
        for cx, cy, start in ((x+w/2-r, y+h/2-r, 0), (x-w/2+r, y+h/2-r, 90),
                              (x-w/2+r, y-h/2+r, 180), (x+w/2-r, y-h/2+r, 270)):
            for step in range(5):
                angle = math.radians(start + step * 90 / 4)
                coordinates.append((cx + math.cos(angle)*r, cy + math.sin(angle)*r))
        return polygon(name, coordinates, material, record, visible, .04)

    def line_mesh(name, coordinates, thickness, material, record, visible, z):
        vertices, faces = [], []
        for a, b in zip(coordinates, coordinates[1:]):
            dx, dy = b[0]-a[0], b[1]-a[1]
            length = math.hypot(dx, dy)
            if length < .1:
                continue
            nx, ny = -dy/length*thickness/2, dx/length*thickness/2
            n = len(vertices)
            vertices.extend([point(a[0]+nx, a[1]+ny, z), point(a[0]-nx, a[1]-ny, z),
                             point(b[0]-nx, b[1]-ny, z), point(b[0]+nx, b[1]+ny, z)])
            faces.append((n,n+1,n+2,n+3))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name, mesh)
        group.objects.link(obj)
        configure(obj, record, visible)
        return obj

    records = []
    campus = bpy.data.collections['02 Campus buildings']
    for obj in sorted(campus.objects, key=lambda o: int(o.get('osm_id', 0))):
        if obj.type != 'MESH' or 'osm_id' not in obj:
            continue
        tags = json.loads(obj.get('osm_tags', '{}'))
        oid = str(obj['osm_id'])
        choices = ((tags.get('name:zh'), 'OSM name:zh'),
                   (obj.get('name_zh'), 'source name_zh'),
                   (tags.get('name:en'), 'OSM name:en'),
                   (tags.get('name'), 'OSM name'))
        name, source = next(((v, k) for v, k in choices if v and v.strip()),
                            ('建筑' + oid[-6:] + '（无名称）', 'No source name; OSM ID suffix'))
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        roof_z = max(p.z for p in points)
        # A roof face centroid stays inside most irregular footprints, unlike a bbox centre.
        roof_faces = [p for p in obj.data.polygons if p.normal.z > .5]
        if roof_faces:
            roof_face = max(roof_faces, key=lambda p: p.area)
            anchor = obj.matrix_world @ roof_face.center
        else:
            anchor = sum(points, Vector()) / len(points)
        anchor.z = roof_z + .4
        if 'photo_roof_anchor' in obj:
            anchor=Vector(obj['photo_roof_anchor'])+Vector((0,0,.4))
        projected = world_to_camera_view(scene, camera, anchor)
        px, py = projected.x*width, projected.y*height
        visible = projected.z > 0 and 30 < px < width-30 and 40 < py < height-40
        record = dict(osm_id=oid, object_name=obj.name, name=name,
                      name_source=source, anchor_world=list(anchor),
                      named=not source.startswith('No source'),
                      anchor_px=[px, py], visible=visible,
                      area=sum(p.area for p in roof_faces))
        curve = bpy.data.curves.new('Building name ' + oid, 'FONT')
        curve.font = font
        curve.body = _wrap_name(name)
        curve.size = font_px * px_world
        curve.align_x = 'CENTER'
        curve.align_y = 'CENTER'
        curve.space_line = 1.15
        curve.resolution_u = 4
        curve.materials.append(white)
        text = bpy.data.objects.new('Label | ' + name + ' | ' + oid, curve)
        group.objects.link(text)
        # Measure in local axes first; rotation is applied after layout.
        record['text_object'] = text
        records.append(record)
    bpy.context.view_layer.update()
    for record in records:
        text = record['text_object']
        record['box_size'] = (text.dimensions.x/px_world + 24,
                              max(font_px*.86, text.dimensions.y/px_world) + 15)

    visible_records = [r for r in records if r['visible']]
    # The denser central buildings receive first choice of nearby open positions.
    for record in visible_records:
        ax, ay = record['anchor_px']
        record['density'] = sum(math.hypot(ax-r['anchor_px'][0], ay-r['anchor_px'][1]) < 180
                                for r in visible_records)
    ordered = sorted(visible_records,
                     key=lambda r: (-r['named'], -r['density'], -r['area'], r['osm_id']))
    boxes = []
    label_positions = {}
    margin = 22
    for record in ordered:
        ax, ay = record['anchor_px']
        bw, bh = record['box_size']
        candidates = []
        for ring in range(16):
            radius = 36 + ring*30
            for direction in range(24):
                theta = math.pi/2 + direction*math.tau/24
                x = min(width-margin-bw/2, max(margin+bw/2, ax+math.cos(theta)*radius))
                y = min(height-margin-bh/2, max(margin+bh/2, ay+math.sin(theta)*radius))
                box = (x,y,bw,bh)
                if any(_overlap(box, old) for old in boxes):
                    continue
                # Penalize covering another roof anchor; nearby negative space wins.
                roof_hits = sum(abs(x-r['anchor_px'][0]) < bw/2+9 and
                                abs(y-r['anchor_px'][1]) < bh/2+9 for r in visible_records)
                distance = math.hypot(x-ax, y-ay)
                cost = distance + roof_hits*85 + max(0, ay-y)*.10
                candidates.append((cost, box))
            if candidates and ring >= 3:
                break
        if not candidates:
            # A global fallback keeps every in-frame building available at high density.
            for y in range(int(margin+bh/2), int(height-margin-bh/2), 24):
                for x in range(int(margin+bw/2), int(width-margin-bw/2), 42):
                    box = (x,y,bw,bh)
                    if not any(_overlap(box, old) for old in boxes):
                        candidates.append((math.hypot(x-ax,y-ay), box))
        if candidates:
            box = min(candidates, key=lambda v: v[0])[1]
            boxes.append(box)
            label_positions[record['osm_id']] = box
        else:
            record['visible'] = False
            record['not_rendered_reason'] = 'No collision-free screen position at this resolution'

    for record in records:
        oid, text = record['osm_id'], record['text_object']
        ax, ay = record['anchor_px']
        bw, bh = record['box_size']
        box = label_positions.get(oid, (ax, ay+50, bw, bh))
        x,y,bw,bh = box
        visible = record['visible']
        text.location = point(x,y,.065)
        text.rotation_mode = 'QUATERNION'
        text.rotation_quaternion = rotation
        configure(text, record, visible)
        text['full_source_name'] = record['name']
        rounded('Label plate | '+oid, box, navy, record, visible)
        polygon('Label accent | '+oid,
                [(x-bw/2+5,y-bh/2+6),(x-bw/2+8,y-bh/2+6),
                 (x-bw/2+8,y+bh/2-6),(x-bw/2+5,y+bh/2-6)], cyan,
                record, visible, .055)
        # The leader ends at the nearest plate edge, with a short orthogonal elbow.
        ex = min(x+bw/2-7,max(x-bw/2+7,ax))
        ey = y-bh/2 if ay < y else y+bh/2
        if abs(ax-x) > bw/2 and abs(ay-y) < bh/2:
            ex = x-bw/2 if ax < x else x+bw/2
            ey = min(y+bh/2-5,max(y-bh/2+5,ay))
        elbow = (ex, ey + (-9 if ay < ey else 9))
        line_mesh('Leader border | '+oid, [(ax,ay),elbow,(ex,ey)], 3.5,
                  dark_leader, record, visible, -.015)
        line_mesh('Leader | '+oid, [(ax,ay),elbow,(ex,ey)], 1.6,
                  leader_mat, record, visible, -.010)
        dot = [(ax+3*math.cos(i*math.tau/12),ay+3*math.sin(i*math.tau/12)) for i in range(12)]
        polygon('Roof marker | '+oid, dot, white, record, visible, .001)
        record['label_box_px'] = list(box)
    bpy.context.view_layer.update()
    export_records = [{k:v for k,v in record.items() if k != 'text_object'} for record in records]
    stats = dict(total_buildings=len(records), named_buildings=sum(r['named'] for r in records),
                 visible_labels=sum(r['visible'] for r in records), camera=camera.name, mode=mode,
                 font=font.filepath, font_packed=bool(font.packed_file), font_size_px=font_px,
                 overlapping_label_pairs=sum(_overlap(a,b,padding=0) for i,a in enumerate(boxes) for b in boxes[i+1:]),
                 names_source='Existing building OSM tags; source Chinese preferred; unnamed IDs explicitly marked',
                 labels_are_camera_overlay=True)
    group['label_stats'] = json.dumps(stats,ensure_ascii=False)
    group['label_inventory'] = json.dumps(export_records,ensure_ascii=False)
    group['usage'] = 'Re-run apply_building_labels(camera, mode) after changing camera or output resolution. Offscreen objects are retained hidden.'
    print('BUILDING_LABELS',json.dumps(stats,ensure_ascii=False),flush=True)
    return stats
