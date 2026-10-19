"""Create an editable detailed visual model from the existing georeferenced campus."""
import bpy,bmesh,json,sys,math,random
import numpy as np
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parent;sys.path.insert(0,str(root))
bpy.ops.wm.open_mainfile(filepath=str(root/'CUHK_color_materials.blend'))
scene=bpy.context.scene
original={o.name:len(o.data.vertices) for o in bpy.data.objects if o.type=='MESH' and 'height_source' in o}
from detail_buildings import apply_building_details
from detail_site import apply_site_details
stats={}

def mat(name,color,roughness=.75):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1)
    m.node_tree.nodes.clear();bs=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled');bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=roughness
    out=m.node_tree.nodes.new('ShaderNodeOutputMaterial');m.node_tree.links.new(bs.outputs['BSDF'],out.inputs['Surface']);return m
greens=[mat('Canopy / '+str(i),c) for i,c in enumerate([(.024,.10,.025),(.042,.16,.026),(.065,.20,.035),(.10,.24,.046),(.045,.125,.04),(.12,.19,.033)])]
bark=mat('Bark / warm grey',(.14,.10,.063))
group=bpy.data.collections.new('09 Mapped vegetation / illustrative crowns');scene.collection.children.link(group)
def move(o):
    for c in list(o.users_collection):c.objects.unlink(o)
    group.objects.link(o)
grid=np.load(root/'terrain_refined_display.npz');xs,ys=grid['x'],grid['y'];z=grid['elevation']
def height(x,y):
    u=np.clip((np.asarray(x)-xs[0])/5,0,len(xs)-1.00001);v=np.clip((ys[0]-np.asarray(y))/5,0,len(ys)-1.00001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    # Match the terrain's explicit A-C triangle diagonal, avoiding bilinear/mesh disagreement.
    return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o)
co=np.empty(len(terrain.data.vertices)*3,dtype=np.float32);terrain.data.vertices.foreach_get('co',co);co=co.reshape(-1,3);co[:,2]=z.ravel()
nx=len(xs);ny=len(ys);faces=[]
for r in range(ny-1):
    for c in range(nx-1):
        a=r*nx+c;b=(r+1)*nx+c;cc=b+1;d=a+1;faces.extend(((a,b,cc),(a,cc,d)))
old=terrain.data;new=bpy.data.meshes.new('Refined platform terrain / exact triangular sampling');new.from_pydata(co.tolist(),[],faces);new.materials.append(old.materials[0]);terrain.data=new
for poly in new.polygons:poly.use_smooth=True
terrain['display_refinement']='Illustrative building and sport platform leveling. Original source DTM remains in terrain.npz.'
featuremap={str(f['id']):f for f in json.loads((root/'geodata.json').read_text('utf-8'))['features']}
for groupname in ('04 Roads and paths','05 Water and sport'):
    for o in bpy.data.collections[groupname].objects:
        if o.type!='MESH' or 'osm_id' not in o:continue
        oid=str(o['osm_id'])
        if oid=='0':continue
        f=featuremap.get(oid)
        if not f:continue
        # Shorter triangles follow the five-metre terrain changes at sloping road edges.
        if f['kind']=='road':
            bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.subdivide_edges(bm,edges=list(bm.edges),cuts=1,use_grid_fill=True);bm.to_mesh(o.data);bm.free()
        offset=(.8+.002*(int(oid)%101)) if f['kind']=='road' else 1.3 if f['tags'].get('leisure')=='track' else 1.5 if f['tags'].get('leisure')=='swimming_pool' else 1.0
        co=np.empty(len(o.data.vertices)*3,dtype=np.float32);o.data.vertices.foreach_get('co',co);co=co.reshape(-1,3);co[:,2]=height(co[:,0],co[:,1])+offset;o.data.vertices.foreach_set('co',co.ravel());o.data.update()
stats={'building_details':apply_building_details(),'site_details':apply_site_details(height_fn=height)}
for o in bpy.data.collections.get('08 Site details',[]).objects if bpy.data.collections.get('08 Site details') else []:
    o['placement_source']='OSM plan geometry; sampled to refined illustrative platform terrain'
rng=random.Random(109)
templates=[]
# Eight shared crown meshes give varied silhouettes with modest memory cost.
for variant in range(8):
    pieces=[]
    for k,(cx,cy,cz,sx,sy,sz) in enumerate([(0,0,.68,.75,.75,.29),(-.35,.10,.61,.60,.52,.28),(.34,-.07,.69,.52,.61,.30),(.02,.28,.82,.57,.57,.23)]):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2,radius=1,location=(cx,cy,cz));o=bpy.context.object;o.scale=(sx,sy,sz)
        for vertex in o.data.vertices:vertex.co*=rng.uniform(.91,1.08)
        o.data.materials.append(greens[(variant+k)%len(greens)])
        for poly in o.data.polygons:poly.use_smooth=True
        pieces.append(o)
    bpy.ops.mesh.primitive_cone_add(vertices=7,radius1=.075,radius2=.037,depth=.65,location=(0,0,.30));o=bpy.context.object;o.data.materials.append(bark);pieces.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in pieces:o.select_set(True)
    bpy.context.view_layer.objects.active=pieces[0];bpy.ops.object.join();o=bpy.context.object
    bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    o.name='Shared tree crown '+str(variant);templates.append(o.data);bpy.data.objects.remove(o,do_unlink=True)
tree_data=json.loads((root/'vegetation_points.json').read_text('utf-8'))
for i,t in enumerate(tree_data['trees']):
    o=bpy.data.objects.new(f'Tree {i:05d}',templates[i%8]);group.objects.link(o)
    o.location=(t['x'],t['y'],height(t['x'],t['y'])-.8);o.scale=(t['r'],t['r']*rng.uniform(.85,1.1),t['h']);o.rotation_euler.z=rng.uniform(0,math.tau)
    o['placement_source']=t['source'];o['appearance']='Illustrative crown; woodland scatter positions are not individual surveyed trees'
stats['vegetation']={'trees':len(tree_data['trees']),'shared_crown_meshes':8,'OSM_timestamp':tree_data['source_timestamp']}

# A quieter ground shader allows the three-dimensional vegetation and architecture to read clearly.
ground=mat('Refined ground / meadow and soil',(.12,.20,.055))
n=ground.node_tree.nodes;l=ground.node_tree.links;bs=next(a for a in n if a.type=='BSDF_PRINCIPLED')
geo=n.new('ShaderNodeNewGeometry');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.016;noise.inputs['Detail'].default_value=2;l.new(geo.outputs['Position'],noise.inputs['Vector'])
ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.065,.14,.038,1);ramp.color_ramp.elements[1].color=(.19,.26,.083,1)
l.new(noise.outputs['Fac'],ramp.inputs['Fac']);l.new(ramp.outputs['Color'],bs.inputs['Base Color'])
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o);terrain.data.materials[0]=ground
water=mat('Refined water / calm teal',(.018,.17,.235),.19)
n=water.node_tree.nodes;l=water.node_tree.links;bs=next(a for a in n if a.type=='BSDF_PRINCIPLED');bs.inputs['Metallic'].default_value=.08
geo=n.new('ShaderNodeNewGeometry');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.17;noise.inputs['Detail'].default_value=2;l.new(geo.outputs['Position'],noise.inputs['Vector'])
bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.24;bump.inputs['Distance'].default_value=.055;l.new(noise.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],bs.inputs['Normal'])
for o in bpy.data.objects:
    if o.type!='MESH':continue
    for i,m in enumerate(o.data.materials):
        if m.name.startswith('Water / turquoise'):o.data.materials[i]=water

# A small edge bevel affects shading only and leaves geographic meshes unchanged.
for o in bpy.data.collections['02 Campus buildings'].objects:
    if o.type=='MESH':
        bevel=o.modifiers.new('Architectural edge highlight','BEVEL');bevel.width=.07;bevel.segments=2
sun=bpy.data.objects['Sun / northwest'];sun.data.energy=3.4;sun.data.color=(1,.91,.78);sun.data.angle=.10
background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND');background.inputs[0].default_value=(.50,.62,.77,1);background.inputs[1].default_value=.42
bpy.data.objects['Legend'].data.body='DETAILED VISUAL MODEL / FACADES AND CROWNS ARE ILLUSTRATIVE'
scene['README']='Detailed visual model from LandsD terrain and OSM footprints. Windows, facade rhythm, roof equipment, platform leveling and tree crowns are illustrative. Woodland scatter uses mapped areas. Original terrain retained. Building height-source properties remain authoritative. See REFINEMENT.md.'
scene['appearance_note']='Materials and added details are illustrative, not a surveyed architectural reconstruction.'
bpy.ops.object.camera_add(location=(690,-780,720));close=bpy.context.object;close.name='Camera / core architectural detail';close.rotation_euler=(Vector((-80,-65,110))-close.location).to_track_quat('-Z','Y').to_euler();close.data.type='ORTHO';close.data.ortho_scale=930;close.data.clip_end=15000
for c in list(close.users_collection):c.objects.unlink(close)
bpy.data.collections['06 Presentation'].objects.link(close)
scene.render.engine='CYCLES';scene.cycles.samples=192;scene.cycles.use_adaptive_sampling=True;scene.cycles.adaptive_threshold=.012;scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX';prefs.get_devices()
    if any(d.type=='OPTIX' for d in prefs.devices):
        for d in prefs.devices:d.use=d.type=='OPTIX'
        scene.cycles.device='GPU'
except Exception as e:print('CPU fallback',e,flush=True)
scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGB';scene.view_settings.view_transform='AgX';scene.view_settings.exposure=.30
scene.camera=close;scene.render.resolution_x=3000;scene.render.resolution_y=2200;scene.render.resolution_percentage=100
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=1100;area.spaces.active.region_3d.view_location=(-80,-65,110);area.spaces.active.region_3d.view_rotation=close.rotation_euler.to_quaternion();area.spaces.active.shading.type='MATERIAL'
assert all(len(bpy.data.objects[k].data.vertices)==v for k,v in original.items()),'Source building geometry changed'
assert len(original)==370 and stats['vegetation']['trees']>500
stats['source_buildings_preserved']=len(original)
(root/'refinement_stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
print('REFINEMENT_STATS',stats,flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(root/'CUHK_refined.blend'))
scene.render.filepath=str(root/'CUHK_refined_closeup.png');bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Camera / southeast overview'];scene.render.resolution_x=3200;scene.render.resolution_y=2800
scene.render.filepath=str(root/'CUHK_refined_overview.png');bpy.ops.render.render(write_still=True)
print('REFINEMENT_COMPLETE',flush=True)
