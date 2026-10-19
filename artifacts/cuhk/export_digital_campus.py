"""Export terrain for Digital Campus; retain the corrected Blender source unchanged.

Run in Blender, then run tools/gltf/build_digital_campus.mjs in Node. Buildings,
roads and sports are derived from the already validated web GLB, never rebuilt.
"""
import json
import sys
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from export_web import coordinates, terrain_copy, mesh_from_arrays
from export_ue5 import selected_geometry, simple_material

SOURCE = ROOT / 'CUHK_shaw_science_corrected.blend'
OUT = ROOT.parents[1] / 'cuhk-campus-web/public/campus'
STAGE = ROOT / 'audits/digital_campus/stage'
OUT.mkdir(parents=True, exist_ok=True)
STAGE.mkdir(parents=True, exist_ok=True)
stamp = (SOURCE.stat().st_mtime_ns, SOURCE.stat().st_size)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
geometry = selected_geometry(bpy.context.scene)
terrain = next(o for g,o in geometry if g == '01' and 'horizontal_crs' in o)
scratch = bpy.data.collections.new('Digital Campus export scratch')
bpy.context.scene.collection.children.link(scratch)
material = simple_material(terrain.data.materials[0], {}, {})
building_shells = []
material_cache, palette = {}, {}
for group, source in geometry:
    if group not in {'02','03'} or 'osm_id' not in source:
        continue
    mesh = source.data.copy()
    mesh.transform(source.matrix_world)
    for i, mat in enumerate(mesh.materials):
        mesh.materials[i] = simple_material(mat, palette, material_cache)
    obj = bpy.data.objects.new('web_building_'+str(source['osm_id']),mesh)
    obj['osm_id']=str(source['osm_id']); obj['category']='building'
    scratch.objects.link(obj); building_shells.append(obj)
bpy.ops.object.select_all(action='DESELECT')
for obj in building_shells: obj.select_set(True)
bpy.context.view_layer.objects.active=building_shells[0]
bpy.ops.export_scene.gltf(filepath=str(STAGE/'building-shells.glb'),export_format='GLB',use_selection=True,
    export_yup=True,export_extras=True,export_cameras=False,export_lights=False,
    export_animations=False,export_texcoords=False,export_draco_mesh_compression_enable=False)
# Keep exact 1 m triangles at every road, sport surface and the corrected Shaw
# footprint. Elsewhere use the existing stitched 8 m terrain exporter; both
# resolutions are samples of the latest corrected terrain, never new elevation.
protected = [(g,o) for g,o in geometry if g in {'04','05'} or str(o.get('osm_id','')) == '107139044']
surface, report = terrain_copy(terrain, protected, scratch, material, halo_blocks=0, road_triangle_coverage=True)
report.pop('near_road_sport_building_heights_changed', None)
report['protected_road_sport_shaw_heights_changed'] = False
report['other_terrain_resolution_m'] = 8
points = coordinates(surface.data)
surface.data.calc_loop_triangles()
triangles = np.empty((len(surface.data.loop_triangles),3), np.int32)
surface.data.loop_triangles.foreach_get('vertices',triangles.ravel())
normals = np.empty((len(surface.data.vertices),3), np.float32)
surface.data.vertices.foreach_get('normal',normals.ravel())
centers = points[triangles].mean(axis=1)
tiles = []
for row in range(4):
    for col in range(4):
        mask = ((np.clip(((centers[:,0]+1200)//600).astype(int),0,3) == col) &
                (np.clip(((centers[:,1]+1200)//600).astype(int),0,3) == row))
        unique, inverse = np.unique(triangles[mask], return_inverse=True)
        mesh = mesh_from_arrays(f'Terrain tile {row}-{col}',points[unique],inverse.reshape(-1,3),material)
        mesh.normals_split_custom_set_from_vertices(normals[unique].tolist())
        obj = bpy.data.objects.new(f'terrain_{row}_{col}',mesh)
        obj['category']='terrain'; scratch.objects.link(obj)
        bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
        bpy.context.view_layer.objects.active=obj
        filename=f'terrain_{row}_{col}.glb'
        bpy.ops.export_scene.gltf(filepath=str(STAGE/filename),export_format='GLB',use_selection=True,
            export_yup=True,export_extras=True,export_cameras=False,export_lights=False,
            export_animations=False,export_texcoords=False,export_draco_mesh_compression_enable=False)
        tiles.append(dict(file=filename,triangles=int(mask.sum())))
grid = coordinates(terrain.data).reshape(2401,2401,3)
# In glTF, z=-BlenderY. Original grid rows already run north -> south.
heights = np.array([[grid[r:min(r+21,2401),c:min(c+21,2401),2].max()
                    for c in range(0,2401,20)] for r in range(0,2401,20)]).astype(float).round(3)
field=dict(xmin=-1200,zmin=-1200,step=20,rows=121,cols=121,heights=heights.ravel().tolist(),
           sampling='Conservative maximum of each 20 m cell, for camera clearance only')
(OUT/'heightfield.json').write_text(json.dumps(field,separators=(',',':')),encoding='utf-8')
assert stamp == (SOURCE.stat().st_mtime_ns,SOURCE.stat().st_size)
assert sum(t['triangles'] for t in tiles) == len(triangles)
report.update(source=str(SOURCE),source_unchanged=True,tiles=tiles,ground='heightfield.json')
(STAGE/'terrain_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('DIGITAL_TERRAIN_READY',json.dumps(report),flush=True)
