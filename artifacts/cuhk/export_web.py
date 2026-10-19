"""Export the current CUHK Blender scene as two browser-ready Draco GLBs.

Source is read only. Keep 1 m terrain near roads, sports, and buildings; stitch
coarser distant terrain to the exact patches. Blender handles glTF Y-up axes.
"""
import json
import math
import struct
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_ue5 import selected_geometry, simple_material

OUT = ROOT.parents[1] / "cuhk-campus-web" / "public" / "model"
SOURCE = ROOT / "CUHK_shaw_science_corrected.blend"


def coordinates(mesh, matrix=None):
    points = np.empty((len(mesh.vertices), 3), np.float32)
    mesh.vertices.foreach_get("co", points.ravel())
    if matrix is not None:
        m = np.asarray(matrix, dtype=np.float32)
        points = points @ m[:3, :3].T + m[:3, 3]
    return points


def mesh_from_arrays(name, points, triangles, material):
    mesh = bpy.data.meshes.new(name)
    mesh.vertices.add(len(points))
    mesh.vertices.foreach_set("co", np.asarray(points, np.float32).ravel())
    mesh.loops.add(len(triangles) * 3)
    mesh.loops.foreach_set("vertex_index", np.asarray(triangles, np.int32).ravel())
    mesh.polygons.add(len(triangles))
    mesh.polygons.foreach_set("loop_start", np.arange(len(triangles), dtype=np.int32) * 3)
    mesh.polygons.foreach_set("loop_total", np.full(len(triangles), 3, np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(triangles), bool))
    mesh.materials.append(material)
    mesh.update()
    return mesh


def terrain_copy(source, geometry, collection, material, halo_blocks=1, road_triangle_coverage=False):
    """Protected blocks keep original triangles. Shared boundaries have no cracks."""
    grid = coordinates(source.data).reshape(2401, 2401, 3)
    step, blocks = 8, 300
    protect = np.zeros((blocks, blocks), bool)
    for group, obj in geometry:
        if group not in {"02", "03", "04", "05", "11"} or obj.type != "MESH":
            continue
        if group == "05" and any(t in obj.name.lower() for t in ("lake", "harbour", "water")):
            continue
        points = coordinates(obj.data, obj.matrix_world)
        if group == "04":
            # Source road meshes have dense edge samples; entire road width is
            # covered by one block of halo on all sides, including shared nodes.
            rr = np.clip(((1200 - points[:, 1]) // step).astype(int), 0, blocks - 1)
            cc = np.clip(((points[:, 0] + 1200) // step).astype(int), 0, blocks - 1)
            protect[rr, cc] = True
            if road_triangle_coverage:
                obj.data.calc_loop_triangles()
                indices = np.empty((len(obj.data.loop_triangles), 3), np.int32)
                obj.data.loop_triangles.foreach_get('vertices', indices.ravel())
                low = points[indices, :2].min(axis=1)
                high = points[indices, :2].max(axis=1)
                c0 = np.clip(((low[:, 0] + 1200) // step).astype(int), 0, blocks - 1)
                c1 = np.clip(((high[:, 0] + 1200) // step).astype(int), 0, blocks - 1)
                r0 = np.clip(((1200 - high[:, 1]) // step).astype(int), 0, blocks - 1)
                r1 = np.clip(((1200 - low[:, 1]) // step).astype(int), 0, blocks - 1)
                for dr in range(int((r1-r0).max()) + 1):
                    for dc in range(int((c1-c0).max()) + 1):
                        valid = (r0+dr <= r1) & (c0+dc <= c1)
                        protect[r0[valid]+dr, c0[valid]+dc] = True
        else:
            lo, hi = points.min(axis=0), points.max(axis=0)
            c0, c1 = np.clip(((np.array([lo[0], hi[0]]) + 1200) // step).astype(int), 0, blocks - 1)
            r0, r1 = np.clip(((1200 - np.array([hi[1], lo[1]])) // step).astype(int), 0, blocks - 1)
            protect[r0:r1 + 1, c0:c1 + 1] = True
    halo = protect.copy()
    for dr in range(-halo_blocks, halo_blocks + 1):
        for dc in range(-halo_blocks, halo_blocks + 1):
            r0, r1 = max(0, dr), min(blocks, blocks + dr)
            c0, c1 = max(0, dc), min(blocks, blocks + dc)
            halo[r0:r1, c0:c1] |= protect[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
    protect = halo
    triangles = []
    dense = np.arange(step)[:, None] * 2401 + np.arange(step)[None, :]
    dense = dense.ravel()
    for br in range(blocks):
        r = br * step
        for bc in range(blocks):
            c = bc * step
            if protect[br, bc]:
                a = dense + r * 2401 + c
                triangles.extend(np.column_stack((a, a + 2401, a + 2402)).tolist())
                triangles.extend(np.column_stack((a, a + 2402, a + 1)).tolist())
                continue
            # Clockwise ring in row/column coordinates is CCW in world XY.
            top = 1 if br > 0 and protect[br - 1, bc] else step
            right = 1 if bc + 1 < blocks and protect[br, bc + 1] else step
            bottom = 1 if br + 1 < blocks and protect[br + 1, bc] else step
            left = 1 if bc > 0 and protect[br, bc - 1] else step
            ring = [(r + j, c) for j in range(0, step, left)]
            ring += [(r + step, c + j) for j in range(0, step, bottom)]
            ring += [(r + j, c + step) for j in range(step, 0, -right)]
            ring += [(r, c + j) for j in range(step, 0, -top)]
            ids = [row * 2401 + col for row, col in ring]
            center = (r + step // 2) * 2401 + c + step // 2
            triangles.extend((center, ids[i], ids[(i + 1) % len(ids)]) for i in range(len(ids)))
    triangles = np.asarray(triangles, np.int32)
    unique, inverse = np.unique(triangles, return_inverse=True)
    points = grid.reshape(-1, 3)[unique]
    mesh = mesh_from_arrays("Terrain adaptive web", points, inverse.reshape(-1, 3), material)
    # Retain original smooth normals so adjacent dense/sparse patches shade alike.
    normals = np.empty((len(source.data.vertices), 3), np.float32)
    source.data.vertices.foreach_get("normal", normals.ravel())
    mesh.normals_split_custom_set_from_vertices(normals[unique].tolist())
    obj = bpy.data.objects.new("web_terrain", mesh)
    obj["category"] = "terrain"
    obj["source_grid_m"] = 1
    collection.objects.link(obj)
    report = {"source_triangles": len(source.data.polygons), "web_triangles": len(triangles),
              "protected_1m_blocks": int(protect.sum()), "total_8m_blocks": int(protect.size),
              "protected_area_m2": int(protect.sum() * step * step),
              "near_road_sport_building_heights_changed": False,
              "original_diagonals_preserved_in_protected_blocks": True,
              "shared_boundary_vertices_stitched": True, "coarse_block_size_m": step}
    report['road_triangle_bounds_protected'] = road_triangle_coverage
    print("TERRAIN_READY", json.dumps(report), flush=True)
    return obj, report


def join(objects, name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    if len(objects) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    return obj


def write_glb(path, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    result = bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", use_selection=True,
        export_yup=True, export_extras=True, export_cameras=False, export_lights=False,
        export_animations=False, export_materials="EXPORT", export_normals=True,
        export_texcoords=False, export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=24,
        export_draco_normal_quantization=12,
        export_draco_color_quantization=12,
        export_draco_generic_quantization=16)
    assert result == {"FINISHED"} and path.stat().st_size > 100
    return {"file": path.name, "bytes": path.stat().st_size, "objects": len(objects),
            "triangles": sum(len(obj.data.loop_triangles) for obj in objects),
            "vertices": sum(len(obj.data.vertices) for obj in objects)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    stat = SOURCE.stat()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    geometry = selected_geometry(scene)
    for _, obj in geometry:
        for modifier in obj.modifiers:
            modifier.show_viewport = modifier.show_render
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    scratch = bpy.data.collections.new("Web export copies")
    scene.collection.children.link(scratch)
    materials, cache = {}, {}
    terrain = next(obj for group, obj in geometry if group == "01" and "horizontal_crs" in obj)
    terrain_obj, terrain_report = terrain_copy(terrain, geometry, scratch,
                                               simple_material(terrain.data.materials[0], materials, cache))
    buckets = defaultdict(list)
    bounds = {}
    groups_report = defaultdict(lambda: {"source_objects": 0, "triangles": 0})
    flipped = 0
    inventories = {str(row["osm_id"]): row for row in json.loads((ROOT / "building_inventory.json").read_text(encoding="utf-8"))}
    feature_map = {str(f["id"]): f for f in json.loads((ROOT / "geodata.json").read_text(encoding="utf-8"))["features"] if f["kind"] == "building"}
    sources = {}
    for _, obj in geometry:
        if "osm_id" in obj and str(obj["osm_id"]) in inventories and "height_m" in obj:
            sources[str(obj["osm_id"])] = obj
    for index, (group, source) in enumerate(geometry):
        if source == terrain:
            continue
        evaluated = source.evaluated_get(graph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=graph)
        if not len(mesh.vertices) or not len(mesh.polygons):
            bpy.data.meshes.remove(mesh)
            continue
        mesh.transform(evaluated.matrix_world)
        if group == "05" or evaluated.matrix_world.determinant() < 0:
            bm = bmesh.new()
            bm.from_mesh(mesh)
            faces = list(bm.faces) if evaluated.matrix_world.determinant() < 0 else [f for f in bm.faces if f.normal.z < 0]
            flipped += len(faces)
            bmesh.ops.reverse_faces(bm, faces=faces)
            bm.to_mesh(mesh)
            bm.free()
        # Clearing slots resets every polygon to slot 0 in Blender. Replace
        # them in place so glazing, trims, roofs, and walls stay distinct.
        material_indices = np.empty(len(mesh.polygons), dtype=np.int32)
        mesh.polygons.foreach_get("material_index", material_indices)
        mapped = [simple_material(m, materials, cache) for m in mesh.materials]
        for slot, material in enumerate(mapped):
            mesh.materials[slot] = material
        if not mapped:
            mesh.materials.append(simple_material(None, materials, cache))
        current_indices = np.empty_like(material_indices)
        mesh.polygons.foreach_get("material_index", current_indices)
        assert np.array_equal(current_indices, material_indices), source.name
        copy = bpy.data.objects.new("web_copy", mesh)
        copy.matrix_world = Matrix.Identity(4)
        scratch.objects.link(copy)
        building_id = str(source.get("osm_id", ""))
        if building_id in inventories and group in {"02", "03", "07", "11"}:
            bucket = "web_building_" + building_id
            points = coordinates(mesh)
            lo, hi = points.min(axis=0), points.max(axis=0)
            if building_id in bounds:
                oldlo, oldhi = bounds[building_id]
                lo, hi = np.minimum(lo, oldlo), np.maximum(hi, oldhi)
            bounds[building_id] = lo, hi
            copy["osm_id"] = building_id
            copy["category"] = "building"
        else:
            bucket = "web_site_" + group
            copy["category"] = {"01": "terrain", "04": "roads", "05": "sports_water", "09": "vegetation", "14": "road_foundations"}.get(group, "details")
        copy["collection_group"] = group
        mesh.calc_loop_triangles()
        groups_report[group]["source_objects"] += 1
        groups_report[group]["triangles"] += len(mesh.loop_triangles)
        buckets[bucket].append(copy)
        if index % 300 == 0:
            print("COPY", index, "/", len(geometry), flush=True)
    campus = []
    for name, objects in buckets.items():
        obj = join(objects, name)
        if name == "web_site_14":
            # Dissolve coplanar slab tessellation without changing road-top mesh.
            modifier = obj.modifiers.new("Remove redundant slab subdivisions", "DECIMATE")
            modifier.decimate_type = "DISSOLVE"
            modifier.angle_limit = math.radians(0.25)
            modifier.delimit = {"MATERIAL"}
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        obj.data.calc_loop_triangles()
        campus.append(obj)
    terrain_obj.data.calc_loop_triangles()
    terrain_objects = [terrain_obj] + [o for o in campus if o.get("category") == "terrain"]
    campus = [o for o in campus if o not in terrain_objects]
    material_triangles = {}
    for obj in campus:
        counts = defaultdict(int)
        for triangle in obj.data.loop_triangles:
            counts[obj.data.materials[triangle.material_index].name] += 1
        material_triangles[obj.name] = dict(counts)
    buildings = []
    for building_id, (lo, hi) in bounds.items():
        inventory = inventories[building_id]
        tags = feature_map.get(building_id, {}).get("tags", {})
        original = sources.get(building_id)
        center = (lo + hi) * 0.5
        size = hi - lo
        row = {"id": building_id, "name": tags.get("name:en") or inventory["name"],
               "name_zh": tags.get("name:zh-Hans") or tags.get("name:zh") or "",
               "position": [float(center[0]), float(center[2]), float(-center[1])],
               "size": [float(size[0]), float(size[2]), float(size[1])],
               "height_m": float(original.get("height_m", inventory["height_m"])) if original else inventory["height_m"],
               "height_source": original['height_source'] if original and original.get('height_source') == 'lidar_photo_estimate' else inventory["height_source"], "campus": inventory["campus"],
               "mesh_name": "web_building_" + building_id}
        if original and original.get('height_note'):
            row['height_note'] = original['height_note']
            row['height_source_url'] = original.get('height_source_url', '')
            row['storeys'] = int(original.get('building_storeys',0))
        buildings.append(row)
    # All source geometry is disposable in this process. Source .blend is never saved.
    keep = set(terrain_objects + campus)
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.orphans_purge(do_recursive=True)
    files = []
    for name, objects in [("terrain.glb", terrain_objects), ("campus.glb", campus)]:
        print("EXPORTING", name, len(objects), flush=True)
        files.append(write_glb(OUT / name, objects))
        print("EXPORTED", json.dumps(files[-1]), flush=True)
    (OUT / "buildings.json").write_text(json.dumps(sorted(buildings, key=lambda row: row["id"]), ensure_ascii=False, indent=2), encoding="utf-8")
    assert (SOURCE.stat().st_size, SOURCE.stat().st_mtime_ns) == (stat.st_size, stat.st_mtime_ns)
    report = {"source": str(SOURCE), "source_unchanged": True,
              "generated_utc": datetime.now(timezone.utc).isoformat(),
              "coordinate_conversion": "Blender (x,y,z) metres -> glTF/Three.js (x,z,-y) metres",
              "files": files, "terrain": terrain_report, "source_groups": dict(groups_report),
              "buildings": len(buildings), "materials": len(materials), "flipped_sports_water_faces": flipped,
              "draco_position_bits": 24, "material_double_sided": True,
              "roads_sports_surface_geometry_simplified": False,
              "campus_material_triangles": material_triangles,
              "note": "Visualization from OSM footprints, CEDD terrain and approximate photo-based facades; not a survey. Hidden original roads, fonts, labels, and presentation objects excluded."}
    (OUT / "export_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WEB_EXPORT_COMPLETE", json.dumps(report), flush=True)


def validate():
    """Decode the produced files, checking real topology and level track heights."""
    report = json.loads((OUT / "export_report.json").read_text(encoding="utf-8"))
    expected_ids = {row["id"] for row in json.loads((OUT / "buildings.json").read_text(encoding="utf-8"))}
    validation = {"files": [], "building_ids_match": False, "track_planes": []}
    for entry in report["files"]:
        data = (OUT / entry["file"]).read_bytes()
        magic, version, length = struct.unpack_from("<4sII", data)
        assert (magic, version, length) == (b"glTF", 2, len(data))
        json_length, kind = struct.unpack_from("<II", data, 12)
        assert kind == 0x4E4F534A
        document = json.loads(data[20:20 + json_length])
        assert all(m.get("doubleSided") for m in document["materials"])
        assert "KHR_draco_mesh_compression" in document["extensionsRequired"]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(OUT / entry["file"]))
        total = 0
        for obj in bpy.data.objects:
            if obj.type != "MESH":
                continue
            obj.data.calc_loop_triangles()
            total += len(obj.data.loop_triangles)
            assert np.isfinite(coordinates(obj.data, obj.matrix_world)).all()
        assert total == entry["triangles"], (entry["file"], total, entry["triangles"])
        validation["files"].append({"file": entry["file"], "decoded_triangles": total,
                                     "draw_calls": sum(len(m["primitives"]) for m in document["meshes"]),
                                     "all_materials_double_sided": True, "finite_vertices": True})
        if entry["file"] == "campus.glb":
            actual_material_triangles = {}
            for mesh in document["meshes"]:
                counts = defaultdict(int)
                for primitive in mesh["primitives"]:
                    name = document["materials"][primitive["material"]]["name"]
                    counts[name] += document["accessors"][primitive["indices"]]["count"] // 3
                actual_material_triangles[mesh["name"]] = dict(counts)
            # Mesh datablock names can differ from exported object names.
            actual_by_node = {node["name"]: actual_material_triangles[document["meshes"][node["mesh"]]["name"]]
                              for node in document["nodes"] if "mesh" in node}
            assert actual_by_node == report["campus_material_triangles"]
            library = actual_by_node["web_building_134410449"]
            assert any("glaz" in name.lower() or "glass" in name.lower() for name in library), library
            assert any("roof" in name.lower() for name in library), library
            assert any("Photo_ShadowGlazing" in name for counts in actual_by_node.values() for name in counts)
            validation["material_assignment_preserved"] = True
            validation["used_campus_materials"] = len({name for counts in actual_by_node.values() for name in counts})
            validation["library_material_triangles"] = library
            actual_ids = {str(o["osm_id"]) for o in bpy.data.objects if "osm_id" in o}
            assert actual_ids == expected_ids
            validation["building_ids_match"] = True
            shaw = bpy.data.objects['web_building_107139044']
            shaw_points = coordinates(shaw.data, shaw.matrix_world)
            shaw_top = float(shaw_points[:, 2].max())
            assert abs(shaw_top - 117.6) < .001, shaw_top
            roof_vertices = int(np.count_nonzero(np.abs(shaw_points[:, 2] - 111.6) < .001))
            assert roof_vertices >= 20, roof_vertices
            validation['shaw_science'] = {'osm_id': '107139044',
                                         'main_roof_vertices_at_111_6_m': roof_vertices,
                                         'decoded_rooftop_hkpd_m': shaw_top,
                                         'material_triangles': actual_by_node['web_building_107139044']}
            sports = bpy.data.objects.get("web_site_05")
            points = coordinates(sports.data, sports.matrix_world)
            red = {i for i, m in enumerate(sports.data.materials) if "Track_red_rubber" in m.name}
            ids = np.unique([i for p in sports.data.polygons if p.material_index in red for i in p.vertices])
            track_points = points[ids]
            for track_id, xlo, xhi, expected_z in [("955764574", 100, 330, 5.33409977), ("955764585", 370, 600, 23.60296249)]:
                subset = track_points[(track_points[:, 0] > xlo) & (track_points[:, 0] < xhi)]
                assert len(subset) > 100
                error = float(np.max(np.abs(subset[:, 2] - expected_z)))
                assert error < 0.0003, (track_id, error)
                validation["track_planes"].append({"id": track_id, "vertices": len(subset),
                                                     "height_range_m": float(np.ptp(subset[:, 2])),
                                                     "max_height_error_m": error})
    (OUT / "validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WEB_GLB_VALIDATED", json.dumps(validation), flush=True)


if __name__ == "__main__":
    validate() if "--validate" in sys.argv else main()
