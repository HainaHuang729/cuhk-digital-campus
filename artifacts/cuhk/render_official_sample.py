"""Render the independent georeferenced official building sample without changing source meshes."""
import bpy,json,math
from pathlib import Path
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_official_3d_sample.blend'))
scene=bpy.context.scene
report=json.loads((ROOT/'official_3d_sample_report.json').read_text('utf-8'))
models=report['models']
for existing in list(bpy.data.collections):
    if existing.name.startswith('Presentation context / not official geometry'):
        for obj in list(existing.objects):bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(existing)
for model in models:
    group=next(c for c in bpy.data.collections if c.name.endswith(model['id']))
    group['footprint_match']=json.dumps(model['name_match'],ensure_ascii=False)
    if model['name_match']['status']=='high_confidence_footprint_match':
        group.name='Official / '+model['name_match']['name_en']+' / '+model['id']

presentation=bpy.data.collections.new('Presentation context / not official geometry')
scene.collection.children.link(presentation)
def place(obj):
    for col in list(obj.users_collection):col.objects.unlink(obj)
    presentation.objects.link(obj)
    return obj
def material(name,color,roughness=.8):
    mat=bpy.data.materials.new(name)
    mat.use_nodes=True
    mat.node_tree.nodes.clear()
    bsdf=mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
    out=mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=roughness
    mat.node_tree.links.new(bsdf.outputs['BSDF'],out.inputs['Surface'])
    return mat

lo=np.min([m['local_bounds_min'] for m in models],axis=0)
hi=np.max([m['local_bounds_max'] for m in models],axis=0)
center=(lo+hi)/2
grid=np.load(ROOT/'terrain_refined_display.npz')
xs=grid['x'];ys=grid['y'];z=grid['elevation']
ix=np.where((xs>=lo[0]-35)&(xs<=hi[0]+35))[0]
iy=np.where((ys>=lo[1]-35)&(ys<=hi[1]+35))[0]
xx,yy=np.meshgrid(xs[ix],ys[iy]);zz=z[np.ix_(iy,ix)]
verts=np.column_stack((xx.ravel(),yy.ravel(),zz.ravel())).tolist()
ny,nx=zz.shape
faces=[(r*nx+c,(r+1)*nx+c,(r+1)*nx+c+1,r*nx+c+1) for r in range(ny-1) for c in range(nx-1)]
mesh=bpy.data.meshes.new('Existing display terrain crop');mesh.from_pydata(verts,[],faces);mesh.update()
terrain=bpy.data.objects.new('Context terrain / existing 5m display DTM',mesh);presentation.objects.link(terrain)
mesh.materials.append(material('Context / pale olive',(.33,.40,.30)))
for poly in mesh.polygons:poly.use_smooth=True
terrain['accuracy_note']='Context only: cropped existing display DTM, not a component of official imported glTF models.'
terrain.hide_render=True
terrain.hide_set(True)

bpy.ops.object.camera_add(location=Vector(center)+Vector((-280,-460,300)))
camera=place(bpy.context.object);camera.name='Camera / official sample'
target=Vector(center)+Vector((0,0,-5))
camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO';camera.data.ortho_scale=365;camera.data.clip_end=5000
official_vertices=np.asarray([obj.matrix_world@v.co for obj in bpy.data.objects if obj.type=='MESH' and obj.get('official_building_id') for v in obj.data.vertices])
rotation=camera.rotation_euler.to_quaternion()
right=rotation@Vector((1,0,0));up=rotation@Vector((0,1,0))
screen=np.column_stack(((official_vertices-np.asarray(target))@np.asarray(right),(official_vertices-np.asarray(target))@np.asarray(up)))
screen_lo,screen_hi=screen.min(axis=0),screen.max(axis=0)
offset=(screen_lo+screen_hi)/2
shift=right*float(offset[0])+up*float(offset[1])
camera.location+=shift;target+=shift
extent=screen_hi-screen_lo
camera.data.ortho_scale=max(float(extent[0]),float(extent[1])*2000/1500)*1.14
scene.camera=camera
bpy.ops.object.light_add(type='SUN',location=(0,0,800))
sun=place(bpy.context.object);sun.rotation_euler=(math.radians(28),math.radians(-32),math.radians(-32));sun.data.energy=2.1;sun.data.angle=.25
scene.world=bpy.data.worlds.new('Sample daylight');scene.world.use_nodes=True
background=scene.world.node_tree.nodes.get('Background')
if background is None:background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
background.inputs[0].default_value=(.82,.84,.86,1);background.inputs[1].default_value=.8
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=2000;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB'
scene.render.film_transparent=False
scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.35
scene.render.filepath=str(ROOT/'CUHK_official_3d_sample_preview.png')
scene['sample_report']='official_3d_sample_report.json'
scene['presentation_note']='Nine official source assets remain at native relative coordinates and elevations. The optional olive terrain is existing DTM display context.'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=350
            area.spaces.active.region_3d.view_location=target
            area.spaces.active.region_3d.view_rotation=camera.rotation_euler.to_quaternion()
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.clip_end=5000
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_official_3d_sample.blend'))
bpy.ops.render.render(write_still=True)
print('OFFICIAL_SAMPLE_RENDER_COMPLETE',flush=True)
