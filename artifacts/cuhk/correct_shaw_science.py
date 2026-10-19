"""Correct the six-storey hillside laboratory from official photos and LiDAR.

The original Blender scene is retained; this writes a new editable version.
111.6/117.6 are DSM-supported HKPD roof elevations, not surveyed floor levels.
"""
import hashlib, json, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.geometry import convex_hull_2d

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from photo_facades import apply_photo_facades, Builder
from detail_buildings import _material

OID = '107139044'
ROOF, CORE_TOP = 111.6, 117.6
SOURCE = ROOT / 'CUHK_sports_leveled.blend'
OUTPUT = ROOT / 'CUHK_shaw_science_corrected.blend'


def coordinates(ob):
    co = np.empty((len(ob.data.vertices), 3), np.float32)
    ob.data.vertices.foreach_get('co', co.ravel())
    m = np.asarray(ob.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def geometry_hash(ob):
    return hashlib.sha256(coordinates(ob).tobytes()).hexdigest()


bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene
source = next(ob for ob in bpy.data.collections['02 Campus buildings'].objects if str(ob.get('osm_id')) == OID)
protected = {ob.name: geometry_hash(ob) for group in ('04 Roads and paths', '05 Water and sport')
             for ob in bpy.data.collections[group].objects if ob.type == 'MESH'}
before = coordinates(source)
base = float(source['base_elevation_hkpd_m'])
main_height = ROOF - base
glazing_base = base + main_height / 6

# Bake the old vertical alignment before changing only this building's profile.
source.data.transform(source.matrix_world)
source.matrix_world = Matrix.Identity(4)
ground_file = ROOT / 'audits/terrain_shaw_science_corrected_1m.npz'
if not ground_file.exists():
    raise RuntimeError('Prepared terrain correction is required before saving the final model')
terrain_data = np.load(ground_file)
ground = terrain_data['elevation']

old_roof = float(before[:, 2].max())
for vertex in source.data.vertices:
    if abs(vertex.co.z - old_roof) < .05:
        vertex.co.z = ROOF
    else:
        # A continuous footing stays below the 71.485m minimum sampled along
        # the perimeter, including valleys between the original corner vertices.
        vertex.co.z = 71.0
source.data.update()
source['height_m'] = CORE_TOP - base
source['height_source'] = 'lidar_photo_estimate'
source['height_note'] = '六层建筑；主要屋面及两端设备结构参考激光雷达高程，楼层分隔与基底仍为照片辅助估算。模型高度含屋顶设备结构。'
source['height_source_url'] = 'https://www.cpr.cuhk.edu.hk/tc/press/naming-ceremony-of-run-run-shaw-science-building-at-cuhk-held-today/'
source['building_storeys'] = 6
source['facade_storeys'] = 5
source['facade_base_hkpd_m'] = glazing_base
source['main_roof_hkpd_m'] = ROOF
source['core_top_hkpd_m'] = CORE_TOP
source['height_correction'] = 'OSM above-ground 3 + underground 3 describe a hillside building. Official CUHK: six storeys, five laboratory floors. Main roof pinned to CEDD DSM plateau.'

group = bpy.data.collections['11 Photo reference architecture']
for ob in list(group.objects):
    if str(ob.get('osm_id')) == OID:
        bpy.data.objects.remove(ob, do_unlink=True)
reference = next(r for r in json.loads((ROOT/'photo_reference_manifest.json').read_text('utf8')) if str(r['osm_id']) == OID)
facade_records = apply_photo_facades(group, {OID: source}, [reference])
assert facade_records[0]['floors_modeled'] == 5

# Elevated end structures follow the coherent high-return patches, not the
# entire roof. Their exact equipment and louvre arrangement is approximate.
samples = np.load(ROOT/'audits/shaw_elevation_samples.npz')
X,Y = np.meshgrid(samples['x'], samples['y'])
high = samples['footprint'] & (samples['dsm'] > 115)
builder = Builder()
core_reports = []
for name, region in [('west', X < 50), ('east', X > 110)]:
    mask = high & region
    points = [Vector((float(x), float(y))) for x,y in zip(X[mask], Y[mask])]
    hull = [points[i] for i in convex_hull_2d(points)]
    assert len(hull) >= 3
    # The sampled hull is inside the roof footprint, preventing expansion over roads.
    lower = [Vector((p.x,p.y,ROOF+.02)) for p in hull]
    upper = [Vector((p.x,p.y,CORE_TOP)) for p in hull]
    for a,b,c,d in zip(lower,lower[1:]+lower[:1],upper[1:]+upper[:1],upper):
        builder.face([a,b,c,d],0)
        width = (b-a).length
        u = (b-a).normalized(); n = u.cross(Vector((0,0,1)))
        for level in range(12):
            center=(a+b)*.5; center.z=ROOF+.3+level*.45
            builder.box(center+n*.035,u,n,width,.075,.055,1)
    builder.face(upper,0)
    core_reports.append({'end':name,'roof_hkpd_m':CORE_TOP,'footprint_xy':[list(p) for p in hull]})
core = builder.finish('Photo / Shaw Science raised end structures', group, [
    _material('Shaw Science / charcoal roof plant',(.028,.035,.037),.75),
    _material('Shaw Science / louvre frames',(.06,.067,.07),.55,.25)])
core['osm_id'] = OID
core['photo_based'] = True
core['uncertainty'] = 'End footprints are convex hulls of native DSM returns above 115m; 117.6m top and louvres are approximate architectural representation, not surveyed equipment geometry.'

terrain = next(ob for ob in bpy.data.objects if 'horizontal_crs' in ob and ob.type == 'MESH')
assert np.allclose(np.asarray(terrain.matrix_world),np.eye(4))
co = coordinates(terrain).astype(np.float32)
old_terrain = co[:,2].copy()
co[:,2] = ground.ravel()
terrain.data.vertices.foreach_set('co',co.ravel())
terrain.data.update()
terrain['display_grid_path'] = str(ground_file)
terrain['shaw_rear_terrace'] = 'Local restoration toward original DTM, with existing road-clearance terrain protected.'

assert all(geometry_hash(bpy.data.objects[name]) == digest for name,digest in protected.items())
assert abs(max(v.co.z for v in source.data.vertices)-ROOF) < 1e-4
assert source['building_storeys'] == 6
assert all(np.isfinite(coordinates(ob)).all() for ob in (source,core))
from building_labels import apply_building_labels
apply_building_labels(scene.camera,'plan' if scene.camera.data.type == 'ORTHO' and 'plan' in scene.camera.name else 'closeup')
report = {'osm_id':OID,'source_blend':str(SOURCE),'output_blend':str(OUTPUT),
          'old_modeled_height_m':9.9,'old_roof_hkpd_m':old_roof,'main_roof_hkpd_m':ROOF,
          'raised_end_roof_hkpd_m':CORE_TOP,'roof_correction_m':ROOF-old_roof,
          'reference_base_hkpd_m':base,'modeled_height_with_roof_structures_m':CORE_TOP-base,
          'official_storeys':6,'visible_glazing_bands':5,'glazing_base_hkpd_m':glazing_base,
          'facade_records':facade_records,'end_structures':core_reports,
          'foundation_bottom_hkpd_m':float(coordinates(source)[:,2].min()),
          'terrain_vertices_changed':int(np.count_nonzero(np.abs(old_terrain-ground.ravel())>.001)),
          'roads_and_sports_geometry_unchanged':True,
          'height_status':'DSM and photographs support conceptual roof reconstruction; no surveyed architectural floor heights.'}
(ROOT/'SHAW_SCIENCE_CORRECTION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT))
print('SHAW_SCIENCE_CORRECTED',json.dumps(report,ensure_ascii=True),flush=True)
