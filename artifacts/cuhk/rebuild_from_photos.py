"""Build edited scene and source ledger from visually reviewed CUHK photos."""
import bpy, json, sys, math, argparse
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
CACHE=Path.home()/'.agent-reach/cuhk'
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
parser=argparse.ArgumentParser();parser.add_argument('--draft',action='store_true');parser.add_argument('--skip-render',action='store_true');opts=parser.parse_args(args)
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_labeled_smooth_roads.blend'))
scene=bpy.context.scene
mapping=json.loads((CACHE/'photo_sources/named_building_photo_mapping.json').read_text('utf-8'))
raw=json.loads((CACHE/'photo_sources/visual_notes.json').read_text('utf-8'))
for row in mapping:
    official=row.get('official') or {};notes=raw.get(str(row.get('reference_key') or official.get('building_id')),{}).copy()
    model=row.get('model_style')
    if model:
        notes['visible_storeys']=model.get('visible_storeys');notes['window_ratio']=model.get('window_ratio');notes['roof_style']=model.get('roof_style')
    elif row.get('visual_scope')=='source_identity_uncertain':notes={}
    row['appearance_notes']=notes
supp=CACHE/'photo_sources/supplemental_photos.json'
if supp.exists():
    extra=json.loads(supp.read_text('utf-8'));extra={str(v['osm_id']):v for v in extra if v.get('visually_inspected')}
    for row in mapping:
        if str(row['osm_id']) in extra:row.update(extra[str(row['osm_id'])])
group=bpy.data.collections.new('11 Photo reference architecture');scene.collection.children.link(group)
sources={str(o['osm_id']):o for o in bpy.data.collections['02 Campus buildings'].objects if o.type=='MESH' and 'osm_id' in o}
from photo_facades import apply_photo_facades
records=apply_photo_facades(group,sources,mapping)
landmarks={}
if (ROOT/'photo_landmarks.py').exists():
    from photo_landmarks import apply_landmarks
    landmarks=apply_landmarks(group,sources)
    landmark_ids={str(o['osm_id']) for o in landmarks.get('objects',[])}
    for old in bpy.data.collections['07 Building details / illustrative'].objects:
        if str(old.get('osm_id')) in landmark_ids:old.hide_render=True;old.hide_viewport=True
elif not opts.draft:raise RuntimeError('Landmark geometry module is not ready')
for o in group.objects:
    if o.type=='MESH':
        if any(not all(math.isfinite(x) for x in v.co) for v in o.data.vertices):raise RuntimeError('Non-finite photo geometry: '+o.name)
        o.data.validate(verbose=False)
scene['photo_reconstruction_scope']='Photo-guided architectural approximation, not photogrammetric survey. Reference photographs may be historical; unobserved elevations/dimensions remain estimates.'
scene['photo_reference_database']='https://www.cuhk.edu.hk/english/js/campus/cuhk_location_db.js?20161006'
scene['photo_facade_ledger']=json.dumps(records,ensure_ascii=False)
scene['photo_landmark_stats']=json.dumps(landmarks,ensure_ascii=False)
scene['ue5_status']='New geometry ready for FBX export; do not call this scene a UE5 render.'
for o in bpy.data.collections['06 Presentation'].objects:
    if o.type not in {'LIGHT','CAMERA'}:o.hide_render=True
labelgroup=bpy.data.collections['10 Building labels / OSM names'];labelgroup.hide_render=True
scene.render.engine='CYCLES';scene.cycles.samples=48 if opts.draft else 160;scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.014;scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    for d in prefs.devices:d.use=d.type=='OPTIX'
    scene.cycles.device='GPU' if any(d.type=='OPTIX' for d in prefs.devices) else 'CPU'
except Exception as e:print('Cycles setup',e,flush=True)
sun=bpy.data.objects.get('Sun / northwest')
if sun:sun.hide_render=False;sun.data.angle=math.radians(8);sun.data.energy=2.6
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.render.resolution_percentage=100
scene.render.resolution_x=1800 if opts.draft else 3600;scene.render.resolution_y=1350 if opts.draft else 2700
scene.camera=bpy.data.objects['Camera / core architectural detail']
scene.camera.data.ortho_scale=930
bpy.context.view_layer.update()
filename='CUHK_photo_draft' if opts.draft else 'CUHK_photo_rebuilt'
scene.render.filepath=str(ROOT/(filename+'_preview.png'))
result={'named_targets':len(mapping),'photo_guided_facades':sum(r['status']=='photo_guided_facade' for r in records),'design_guided_facades':sum(r['status']=='design_guided_facade' for r in records),'unverified_facades':sum(r['status']=='unverified_exterior' for r in records),'landmarks':landmarks,'records':records,'new_geometry_objects':len(group.objects),'new_geometry_vertices':sum(len(o.data.vertices) for o in group.objects if o.type=='MESH'),'new_geometry_faces':sum(len(o.data.polygons) for o in group.objects if o.type=='MESH')}
(ROOT/'photo_rebuild_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'photo_reference_manifest.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':area.spaces.active.region_3d.view_perspective='CAMERA'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/(filename+'.blend')))
print('PHOTO_BUILD_READY', {k:v for k,v in result.items() if k!='records'},flush=True)
if not opts.skip_render:bpy.ops.render.render(write_still=True)
if not opts.draft:
    from building_labels import apply_building_labels
    labelgroup.hide_render=False
    label_stats=apply_building_labels(scene.camera,'closeup')
    scene.render.filepath=str(ROOT/'CUHK_photo_rebuilt_labeled.png')
    (ROOT/'photo_building_label_inventory.json').write_text(labelgroup['label_inventory'],encoding='utf-8')
    scene['photo_label_stats']=json.dumps(label_stats,ensure_ascii=False)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_photo_rebuilt.blend'))
    if not opts.skip_render:bpy.ops.render.render(write_still=True)
print('PHOTO_BUILD_COMPLETE',flush=True)
