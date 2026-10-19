"""Blender: export a photo-rebuilt CUHK scene into static FBX batches for UE5.

blender --background --python export_ue5.py -- --source CUHK_photo_rebuilt.blend
Add --smoke to export one old/current building into ue5/smoke without touching
the real import manifest. This script never saves or overwrites the source blend.
"""
import argparse
import hashlib
import json
import math
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

ROOT = Path(__file__).resolve().parent
ALLOWED = {"01", "02", "03", "04", "05", "07", "08", "09", "11", "14"}
GEOMETRY_TYPES = {"MESH", "CURVE", "FONT", "SURFACE", "META"}


def selected_geometry(scene):
    found = {}

    def visit(collection, group=None, visible=True):
        visible = visible and not collection.hide_render
        prefix = collection.name[:2]
        if prefix in {"06", "10"}:
            return
        if prefix in ALLOWED:
            group = prefix
        if visible and group:
            for obj in collection.objects:
                if not obj.hide_render and obj.type in GEOMETRY_TYPES:
                    found.setdefault(obj.name, (group, obj))
        for child in collection.children:
            visit(child, group, visible)

    visit(scene.collection)
    return sorted(found.values(), key=lambda pair: (pair[0], pair[1].name))


def simple_material(source, palette, cache):
    original_name = source.name if source else "Unassigned neutral surface"
    if original_name in cache:
        return cache[original_name]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", original_name).strip("_")[:44] or "Surface"
    name = "M_" + slug + "_" + hashlib.sha1(original_name.encode("utf-8")).hexdigest()[:8]
    color, roughness, metallic = [0.5, 0.5, 0.5], 0.7, 0.0
    approximation = "opaque PBR constants"
    if source:
        color = list(source.diffuse_color[:3])
        roughness, metallic = source.roughness, source.metallic
        bs = next((n for n in source.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if source.node_tree else None
        if bs:
            socket = bs.inputs["Base Color"]
            color = list(socket.default_value[:3])
            roughness = bs.inputs["Roughness"].default_value
            metallic = bs.inputs["Metallic"].default_value
            if socket.is_linked:
                node = socket.links[0].from_node
                if node.type == "VALTORGB":
                    color = list(node.color_ramp.evaluate(0.5)[:3])
                    approximation += "; procedural color ramp sampled at midpoint"
                elif node.type == "RGB":
                    color = list(node.outputs[0].default_value[:3])
                else:
                    approximation += "; linked color reduced to authored base constant"
            if bs.inputs["Transmission Weight"].default_value > 0 or bs.inputs["Alpha"].default_value < 1:
                approximation += "; transparent surface represented as opaque architectural material"
    values = {"original_name": original_name,
              "base_color": [max(0.0, min(1.0, float(v))) for v in color],
              "roughness": max(0.0, min(1.0, float(roughness))),
              "metallic": max(0.0, min(1.0, float(metallic))),
              "two_sided": not source.use_backface_culling if source else True,
              "approximation": approximation}
    if not all(math.isfinite(v) for v in values["base_color"] + [values["roughness"], values["metallic"]]):
        raise ValueError(f"Non-finite material values: {original_name}")
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*values["base_color"], 1.0)
    material.use_backface_culling = not values["two_sided"]
    material.use_nodes = True
    bs = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bs.inputs["Base Color"].default_value = material.diffuse_color
    bs.inputs["Roughness"].default_value = values["roughness"]
    bs.inputs["Metallic"].default_value = values["metallic"]
    palette[material.name] = values
    cache[original_name] = material
    return material


def inspect_fbx(path):
    """Read the actual binary with Blender's installed FBX parser; no UE required."""
    from io_scene_fbx import parse_fbx
    root, version = parse_fbx.parse(str(path))
    geometries, vertices, triangles, unit = 0, 0, 0, None
    stack = [root]
    while stack:
        node = stack.pop()
        stack.extend(node.elems)
        if node.id == b"P" and node.props and node.props[0] == b"UnitScaleFactor":
            unit = float(node.props[-1])
        if node.id == b"Geometry" and node.props[-1] == b"Mesh":
            geometries += 1
            for child in node.elems:
                if child.id == b"Vertices":
                    vertices += len(child.props[0]) // 3
                if child.id == b"PolygonVertexIndex":
                    triangles += sum(i < 0 for i in child.props[0])
    if geometries < 1 or vertices < 3 or triangles < 1:
        raise RuntimeError(f"FBX contains no mesh geometry: {path}")
    if unit is None or not math.isclose(unit, 100.0):
        raise RuntimeError(f"Expected meters / UnitScaleFactor 100, got {unit}")
    return {"binary_version": version, "mesh_count": geometries,
            "vertices": vertices, "triangles": triangles, "unit_scale_factor_cm": unit}


def tile_terrain(geometry, collection, cells):
    """Keep the exact 1 m rendered terrain, including its diagonal and normals."""
    revised, report = [], []
    for group, obj in geometry:
        if not (group == "01" and obj.type == "MESH" and "horizontal_crs" in obj):
            revised.append((group, obj))
            continue
        mesh = obj.data
        n = math.isqrt(len(mesh.vertices))
        assert n * n == len(mesh.vertices) and len(mesh.polygons) == 2 * (n - 1) ** 2
        co = np.empty((len(mesh.vertices), 3), np.float32)
        mesh.vertices.foreach_get("co", co.ravel())
        grid = co.reshape(n, n, 3)
        assert np.allclose(np.diff(grid[0, :, 0]), 1.0)
        assert np.allclose(np.diff(grid[:, 0, 1]), -1.0)
        assert np.allclose(grid[:, :, 0], grid[0, :, 0][None, :])
        assert np.allclose(grid[:, :, 1], grid[:, 0, 1][:, None])
        for r, c in [(0, 0), (n // 2, n // 2), (n - 2, n - 2)]:
            face = 2 * (r * (n - 1) + c)
            a = r * n + c
            assert list(mesh.polygons[face].vertices) == [a, a + n, a + n + 1]
            assert list(mesh.polygons[face + 1].vertices) == [a, a + n + 1, a + 1]
        normals = np.empty_like(co)
        mesh.vertices.foreach_get("normal", normals.ravel())
        normals = normals.reshape(n, n, 3)
        count, triangles = 0, 0
        for r in range(0, n - 1, cells):
            for c in range(0, n - 1, cells):
                block = grid[r:min(r + cells + 1, n), c:min(c + cells + 1, n)]
                nr, nc = block.shape[:2]
                a = (np.arange(nr - 1, dtype=np.int32)[:, None] * nc + np.arange(nc - 1, dtype=np.int32)[None]).ravel()
                tri = np.empty((2 * len(a), 3), np.int32)
                tri[0::2] = np.column_stack((a, a + nc, a + nc + 1))
                tri[1::2] = np.column_stack((a, a + nc + 1, a + 1))
                tiled = bpy.data.meshes.new(f"Terrain exact 1m {r:04d}_{c:04d}")
                tiled.vertices.add(nr * nc)
                tiled.vertices.foreach_set("co", np.ascontiguousarray(block).ravel())
                tiled.loops.add(tri.size)
                tiled.loops.foreach_set("vertex_index", tri.ravel())
                tiled.polygons.add(len(tri))
                tiled.polygons.foreach_set("loop_start", np.arange(len(tri), dtype=np.int32) * 3)
                tiled.polygons.foreach_set("loop_total", np.full(len(tri), 3, np.int32))
                tiled.polygons.foreach_set("use_smooth", np.ones(len(tri), bool))
                for mat in mesh.materials:
                    tiled.materials.append(mat)
                tiled.update()
                tiled.normals_split_custom_set_from_vertices(np.ascontiguousarray(normals[r:r + nr, c:c + nc]).reshape(-1, 3).tolist())
                copy = bpy.data.objects.new(f"Terrain 1m tile {r:04d}_{c:04d}", tiled)
                copy.matrix_world = obj.matrix_world.copy()
                collection.objects.link(copy)
                revised.append((group, copy))
                count += 1
                triangles += len(tri)
        assert triangles == len(mesh.polygons)
        report.append({"source_object": obj.name, "grid_spacing_m": 1.0,
                       "tile_cells": cells, "tiles": count, "triangles": triangles,
                       "heights_changed": False, "source_diagonals_preserved": True,
                       "smooth_boundary_normals_preserved": True})
    return revised, report


def camera_manifest(scene):
    from mathutils import Vector
    camera = scene.camera
    forward = camera.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    result = [{"name": "Campus overview", "location_m": list(camera.matrix_world.translation),
               "forward": list(forward), "target_m": [-80, -65, 110],
               "source_camera": camera.name, "type": camera.data.type,
               "ortho_width_m": camera.data.ortho_scale}]
    sports_file = ROOT / "sports_platforms.json"
    if sports_file.exists():
        for f in json.loads(sports_file.read_text(encoding="utf-8"))["facilities"]:
            target = Vector((*f["center_xy"], f["surface_z_m"]))
            result.append({"name": "Stadium " + str(f["track_id"]), "target_m": list(target),
                           "location_m": list(target + Vector((185, -170, 250))),
                           "ortho_width_m": 280 if str(f["track_id"]) == "955764574" else 245})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(ROOT / "CUHK_photo_rebuilt.blend"))
    parser.add_argument("--output-dir", default=str(ROOT / "ue5"))
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--terrain-tile-cells", type=int, default=0)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    source_path = Path(args.source).resolve()
    if not source_path.is_file() or source_path.suffix.lower() != ".blend":
        raise FileNotFoundError(f"Source Blender scene is missing: {source_path}")
    source_stat = source_path.stat()
    output = Path(args.output_dir).resolve()
    if args.smoke:
        output /= "smoke"
    export_dir = output / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source_path))
    scene = bpy.context.scene
    if not math.isclose(scene.unit_settings.scale_length, 1.0):
        raise ValueError("Expected source model coordinates in meters with scale_length=1")
    scene.unit_settings.system = "METRIC"
    geometry = selected_geometry(scene)
    if args.smoke:
        geometry = [next(pair for pair in geometry if pair[0] == "02" and pair[1].type == "MESH")]
    if not geometry:
        raise RuntimeError("No visible geometry found in approved campus collections")
    # Match evaluated geometry to render-enabled modifiers without touching the saved blend.
    for _, obj in geometry:
        for modifier in obj.modifiers:
            modifier.show_viewport = modifier.show_render
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    scratch = bpy.data.collections.new("UE5 export temporary copies")
    scene.collection.children.link(scratch)
    terrain_report = []
    if args.terrain_tile_cells and not args.smoke:
        if not 100 <= args.terrain_tile_cells <= 800:
            raise ValueError("Terrain tile cells must be between 100 and 800")
        geometry, terrain_report = tile_terrain(geometry, scratch, args.terrain_tile_cells)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
    groups = defaultdict(list)
    for group, obj in geometry:
        groups[group].append(obj)
    palette, material_cache, entries, batches = {}, {}, [], []
    global_lo, global_hi = np.full(3, np.inf), np.full(3, -np.inf)
    total_vertices = total_triangles = total_objects = 0
    for group, objects in groups.items():
        batch_size = 1 if group == "01" and args.terrain_tile_cells else 100
        for start in range(0, len(objects), batch_size):
            name = f"SM_CUHK_{group}_{start // batch_size + 1:03d}"
            copies, provenance = [], []
            batch_vertices = batch_triangles = 0
            bpy.ops.object.select_all(action="DESELECT")
            for index, obj in enumerate(objects[start:start + batch_size]):
                evaluated = obj.evaluated_get(depsgraph)
                mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
                if not len(mesh.vertices) or not len(mesh.polygons):
                    bpy.data.meshes.remove(mesh)
                    continue
                mesh.transform(evaluated.matrix_world)
                if evaluated.matrix_world.determinant() < 0:
                    import bmesh
                    bm = bmesh.new()
                    bm.from_mesh(mesh)
                    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
                    bm.to_mesh(mesh)
                    bm.free()
                mapped = [simple_material(mat, palette, material_cache) for mat in mesh.materials]
                # Clearing slots resets polygon material assignments to zero.
                # Keep each slot in place so facade glass/trim/roof survive.
                before = np.empty(len(mesh.polygons), dtype=np.int32)
                mesh.polygons.foreach_get("material_index", before)
                for slot, mat in enumerate(mapped):
                    mesh.materials[slot] = mat
                if not mapped:
                    mesh.materials.append(simple_material(None, palette, material_cache))
                after = np.empty_like(before)
                mesh.polygons.foreach_get("material_index", after)
                assert np.array_equal(before, after), obj.name
                mesh.calc_loop_triangles()
                coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
                mesh.vertices.foreach_get("co", coordinates)
                coordinates = coordinates.reshape(-1, 3)
                if not np.isfinite(coordinates).all():
                    raise RuntimeError(f"Non-finite mesh coordinates: {obj.name}")
                global_lo = np.minimum(global_lo, coordinates.min(axis=0))
                global_hi = np.maximum(global_hi, coordinates.max(axis=0))
                count, tris = len(mesh.vertices), len(mesh.loop_triangles)
                batch_vertices += count
                batch_triangles += tris
                copy = bpy.data.objects.new(f"{name}_Object{index:03d}", mesh)
                copy.matrix_world = Matrix.Identity(4)
                scratch.objects.link(copy)
                copy.select_set(True)
                copies.append(copy)
                provenance.append({"source_object": obj.name, "vertices": count, "triangles": tris})
            if not copies:
                continue
            bpy.context.view_layer.objects.active = copies[0]
            fbx = export_dir / f"{name}.fbx"
            result = bpy.ops.export_scene.fbx(
                filepath=str(fbx), use_selection=True, object_types={"MESH"},
                global_scale=1.0, apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
                axis_forward="-Y", axis_up="Z", use_mesh_modifiers=False,
                use_triangles=True, use_tspace=False, mesh_smooth_type="FACE",
                bake_anim=False, add_leaf_bones=False, use_custom_props=False,
                path_mode="STRIP", embed_textures=False)
            if result != {"FINISHED"} or fbx.stat().st_size < 27:
                raise RuntimeError(f"FBX export failed: {fbx}")
            with fbx.open("rb") as stream:
                if stream.read(23) != b"Kaydara FBX Binary  \x00\x1a\x00":
                    raise RuntimeError(f"Invalid binary FBX header: {fbx}")
            entry = {"file": f"exports/{fbx.name}", "name": name}
            entries.append(entry)
            batch = {**entry, "objects": len(copies), "vertices": batch_vertices,
                     "triangles": batch_triangles, "bytes": fbx.stat().st_size,
                     "source_objects": provenance}
            if args.smoke or not batches:
                batch["parsed_fbx"] = inspect_fbx(fbx)
                if batch["parsed_fbx"]["vertices"] != batch_vertices:
                    raise RuntimeError("Smoke FBX vertex count mismatch")
            batches.append(batch)
            total_vertices += batch_vertices
            total_triangles += batch_triangles
            total_objects += len(copies)
            for copy in copies:
                mesh = copy.data
                bpy.data.objects.remove(copy, do_unlink=True)
                bpy.data.meshes.remove(mesh)
            print(f"EXPORTED {name}: {batch['objects']} objects, {batch_vertices:,} vertices, {batch_triangles:,} triangles", flush=True)
    span = global_hi - global_lo
    if not args.smoke and not (100 < max(span[:2]) < 10000):
        raise RuntimeError(f"Implausible campus extent in meters: {span.tolist()}")
    manifest = {"status": "FBX exported; actual UE5 engine import/render still required",
                "source_scene": str(source_path), "source_scene_mtime": source_path.stat().st_mtime,
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "fbx_files": entries, "materials": palette, "resolution": [3840, 2160],
                "cameras": camera_manifest(scene), "terrain": terrain_report,
                "coordinate_note": "Blender world geometry in meters. FBX -Y forward/Z up; UnitScaleFactor=100 cm. UE import convert_scene=true and convert_scene_unit=true. All mesh origins are identity and actors should be placed at world origin. Validate UE bounds before camera conversion.",
                "material_note": "Opaque linear PBR constants; Blender procedural nodes and glass transmission are approximated."}
    final_stat = source_path.stat()
    unchanged = (source_stat.st_size, source_stat.st_mtime_ns) == (final_stat.st_size, final_stat.st_mtime_ns)
    if not unchanged:
        raise RuntimeError("Source scene changed on disk during export; rerun after modeling finishes")
    report = {"source_scene": str(source_path), "source_file_unchanged": unchanged,
              "smoke_only": args.smoke, "objects": total_objects, "vertices": total_vertices,
              "triangles": total_triangles, "batch_count": len(batches), "material_count": len(palette),
              "bounds_m": {"min": global_lo.tolist(), "max": global_hi.tolist(), "span": span.tolist()},
              "max_objects_per_batch": 100, "nonfinite_vertices": 0,
              "terrain": terrain_report, "included_collection_prefixes": sorted(ALLOWED),
              "excluded_collection_prefixes": ["06", "10"], "hidden_render_objects_excluded": True,
              "batches": batches}
    for filename, data in [("smoke_manifest.json" if args.smoke else "import_manifest.json", manifest),
                           ("export_report.json", report)]:
        target = output / filename
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
    print("CUHK_FBX_SMOKE_COMPLETE" if args.smoke else "CUHK_FBX_EXPORT_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
