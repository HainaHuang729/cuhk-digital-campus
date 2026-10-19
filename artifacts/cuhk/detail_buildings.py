"""Editable illustrative facade details, retaining every source building mesh.

Run apply_building_details() after opening CUHK_color_materials.blend.
Window layout, floor divisions and rooftop equipment are visual estimates.
"""
import json
import math
import re

import bpy
from mathutils import Vector

Z = Vector((0, 0, 1))
GROUP = '07 Building details / illustrative'


def _material(name, color, roughness=.65, metallic=0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bs = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bs is None:
        bs = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output = next((n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if output is None:
            output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bs.outputs['BSDF'], output.inputs['Surface'])
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = roughness
    bs.inputs['Metallic'].default_value = metallic
    return mat


def apply_building_details():
    collection = bpy.data.collections.get(GROUP)
    if collection is None:
        collection = bpy.data.collections.new(GROUP)
        bpy.context.scene.collection.children.link(collection)
    # Re-running replaces only this function's generated detail objects.
    for obj in list(collection.objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    materials = [
        _material('Detail / pale stone window trim', (.52, .54, .48)),
        _material('Detail / dark blue glazing', (.018, .058, .082), .23, .38),
        _material('Detail / reflected sky glazing', (.13, .24, .28), .27, .30),
        _material('Detail / soft neutral glazing', (.072, .13, .145), .30, .28),
        _material('Detail / charcoal metalwork', (.055, .068, .069), .45, .45),
        _material('Detail / rooftop service concrete', (.43, .44, .39), .84),
        _material('Detail / rooftop equipment aluminum', (.36, .40, .40), .48, .55),
    ]
    stats = dict(buildings=0, windows=0, floor_bands=0, parapet_segments=0,
                 roof_equipment=0, entrance_canopies=0, vertices=0, faces=0,
                 illustrative=True, nonfinite_vertices=0)
    campus = bpy.data.collections.get('02 Campus buildings')
    if campus is None:
        raise RuntimeError('Expected source collection: 02 Campus buildings')

    for source in sorted(campus.objects, key=lambda ob: ob.name):
        if source.type != 'MESH' or 'height_source' not in source:
            continue
        tags = json.loads(source.get('osm_tags', '{}'))
        kind = tags.get('building', 'yes')
        if kind in ('roof', 'shed', 'garage', 'garages', 'service'):
            continue
        vertices, faces, indices = [], [], []
        per = dict(windows=0, floor_bands=0, parapet_segments=0,
                   roof_equipment=0, entrance_canopies=0)
        seed = int(source.get('osm_id', '0'))
        transform = source.matrix_world
        normal_transform = transform.to_3x3().inverted().transposed()
        all_points = [transform @ v.co for v in source.data.vertices]
        roof_z = max(p.z for p in all_points)
        floor_z = min(p.z for p in all_points)
        height = roof_z - floor_z
        if height < 4.7:
            continue

        def face(points, material):
            first = len(vertices)
            vertices.extend(tuple(p) for p in points)
            faces.append(tuple(range(first, first + len(points))))
            indices.append(material)

        def panel(center, axis, outward, width, tall, material):
            # axis cross Z faces outward, like the original source wall.
            face([center-axis*width/2-Z*tall/2,
                  center+axis*width/2-Z*tall/2,
                  center+axis*width/2+Z*tall/2,
                  center-axis*width/2+Z*tall/2], material)

        def box(center, axis, outward, width, depth, tall, material):
            first = len(vertices)
            for zsign in (-1, 1):
                for xsign, ysign in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    vertices.append(tuple(center + axis*(xsign*width/2)
                                          + outward*(ysign*depth/2) + Z*(zsign*tall/2)))
            local_faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                           (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            reverse = axis.cross(outward).z < 0
            for f in local_faces:
                faces.append(tuple(first + i for i in (f[::-1] if reverse else f)))
                indices.append(material)

        walls = []
        for poly in source.data.polygons:
            normal = (normal_transform @ poly.normal).normalized()
            if abs(normal.z) > .02 or len(poly.vertices) != 4:
                continue
            points = [all_points[i] for i in poly.vertices]
            bottom = sorted(points, key=lambda p: p.z)[:2]
            a, b = bottom
            delta = b-a
            delta.z = 0
            width = delta.length
            if width < .9:
                continue
            axis = delta.normalized()
            if axis.cross(Z).dot(normal) < 0:
                a, b = b, a
                axis = -axis
            low, high = min(p.z for p in points), max(p.z for p in points)
            walls.append((width, a.copy(), axis, normal, low, high))

        # ponytail: shared storey rhythm is illustrative; surveyed facades can replace
        # individual merged meshes without modifying the original geographic massing.
        level_match = re.search(r'\d+(?:\.\d+)?', str(tags.get('building:levels', '')))
        floors = int(round(float(level_match.group()))) if level_match else round(height/3.4)
        floors = max(1, min(floors, int(height/2.7), 40))
        storey = height / floors
        for wall_index, (width, a, axis, outward, low, high) in enumerate(walls):
            if width > 1.1:
                # The coping sits on the source footprint, inset from its perimeter.
                box(Vector((a.x, a.y, high+.24)) + axis*width/2-outward*.20,
                    axis, outward, width, .32, .48, 0)
                per['parapet_segments'] += 1
            if width < 3.1:
                continue
            bays = max(1, int((width-.7) / (3.05 if kind == 'dormitory' else 3.6)))
            margin = .52
            bay_width = (width-2*margin)/bays
            window_width = min(2.45, bay_width*.65)
            window_height = min(1.95, storey*.52)
            for level in range(floors):
                middle_z = low + level*storey + storey*.53
                if middle_z-window_height/2 < low+.5 or middle_z+window_height/2 > high-.45:
                    continue
                for bay in range(bays):
                    center = a + axis*(margin+(bay+.5)*bay_width)
                    center.z = middle_z
                    box(center+outward*.06, axis, outward,
                        window_width+.16, .12, window_height+.16, 0)
                    glass = 1 + ((seed+wall_index*7+level*3+bay*11) % 7 > 3)
                    if (seed+bay+level*5) % 11 == 0:
                        glass = 3
                    panel(center+outward*.128, axis, outward,
                          window_width, window_height, glass)
                    panel(center+outward*.134, axis, outward,
                          .075, window_height, 4)
                    if window_width > 2.0:
                        panel(center+Z*.18+outward*.135, axis, outward,
                              window_width, .065, 4)
                    box(center-Z*(window_height/2+.10)+outward*.12,
                        axis, outward, window_width+.24, .28, .12, 0)
                    per['windows'] += 1
            for level in range(1, floors):
                center = a+axis*width/2+outward*.035
                center.z = low+level*storey-.08
                box(center, axis, outward, width, .09, .13, 0)
                per['floor_bands'] += 1

        # Give one sufficiently large wall a modest entrance, without inventing stairs
        # or moving the building to fit the terrain.
        if walls:
            width, a, axis, outward, low, high = max(walls, key=lambda wall: wall[0])
            if width > 12 and height > 7:
                center = a+axis*width/2
                center.z = low+1.38
                box(center+outward*.08, axis, outward, 2.6, .15, 2.65, 0)
                panel(center+outward*.162, axis, outward, 2.35, 2.45, 1)
                panel(center+outward*.17, axis, outward, .08, 2.45, 4)
                center.z = low+3.05
                box(center+outward*.70, axis, outward, 3.7, 1.55, .16, 4)
                per['entrance_canopies'] += 1

        # Candidate service boxes must have all four corners and midpoints directly
        # over the original top surface. This rejects courtyard holes and concavities.
        inverse = transform.inverted()
        ray_direction = (inverse.to_3x3() @ -Z).normalized()

        def on_roof(point):
            origin = inverse @ Vector((point.x, point.y, roof_z+100))
            hit, location, normal, index = source.ray_cast(origin, ray_direction)
            return hit and abs((transform @ location).z-roof_z) < .08

        roof_faces = [p for p in source.data.polygons
                      if p.material_index == 1 and (normal_transform @ p.normal).z > .9]
        largest_wall = max(walls, default=None, key=lambda wall: wall[0])
        if largest_wall and sum(p.area for p in roof_faces) > 120:
            axis = largest_wall[2]
            outward = largest_wall[3]
            roof_centers = []
            for poly in sorted(roof_faces, key=lambda p: p.area, reverse=True)[:18]:
                c = sum((all_points[i] for i in poly.vertices), Vector()) / len(poly.vertices)
                if any((c-prior).length < 9 for prior in roof_centers):
                    continue
                wide, deep = (4.2, 3.0) if height > 16 else (3.2, 2.4)
                samples = [c + axis*(sx*(wide/2+.9)) + outward*(sy*(deep/2+.9))
                           for sx, sy in ((-1,-1),(-1,0),(-1,1),(0,-1),(0,0),(0,1),(1,-1),(1,0),(1,1))]
                if not all(on_roof(p) for p in samples):
                    continue
                unit_height = 1.9 if height > 20 else 1.25
                c.z = roof_z+unit_height/2
                box(c, axis, outward, wide, deep, unit_height, 5)
                box(c+Z*(unit_height/2+.06), axis, outward, wide+.18, deep+.18, .12, 6)
                # Visible louver strips on two service-box faces.
                for side in (-1, 1):
                    for stripe in range(4):
                        louver = c+outward*(side*(deep/2+.012))+Z*((stripe-1.5)*.18)
                        panel(louver, axis if side > 0 else -axis,
                              outward*side, wide*.60, .085, 4)
                roof_centers.append(c.copy())
                per['roof_equipment'] += 1
                if len(roof_centers) >= (2 if sum(p.area for p in roof_faces) > 900 else 1):
                    break

        if not vertices:
            continue
        invalid = sum(not all(math.isfinite(value) for value in p) for p in vertices)
        stats['nonfinite_vertices'] += invalid
        if invalid:
            raise ValueError(f'Non-finite detail vertices on {source.name}')
        mesh = bpy.data.meshes.new(source.name + ' / detail mesh')
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        for mat in materials:
            mesh.materials.append(mat)
        for poly, index in zip(mesh.polygons, indices):
            poly.material_index = index
        obj = bpy.data.objects.new(source.name + ' / facade detail', mesh)
        collection.objects.link(obj)
        obj['source_building'] = source.name
        obj['osm_id'] = source.get('osm_id', '')
        obj['illustrative'] = True
        obj['detail_note'] = 'Illustrative window rhythm, copings and roof equipment; not surveyed facades. Original source massing retained.'
        obj['source_height_m'] = source.get('height_m', height)
        obj['height_source'] = source['height_source']
        obj['detail_counts'] = json.dumps(per, sort_keys=True)
        stats['buildings'] += 1
        stats['vertices'] += len(vertices)
        stats['faces'] += len(faces)
        for key, count in per.items():
            stats[key] += count
    assert stats['buildings'] > 100 and stats['windows'] > 1000, stats
    assert stats['nonfinite_vertices'] == 0, stats
    return stats
