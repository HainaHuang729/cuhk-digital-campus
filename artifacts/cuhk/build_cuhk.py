"""blender --background --python build_cuhk.py. Geographic massing, metres, Z up."""
import bpy, bmesh, json, math, re
import numpy as np
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection': bpy.data.collections.remove(c)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1
data=json.loads((ROOT/'geodata.json').read_text('utf-8'))
features=json.loads((ROOT/'meshes.json').read_text('utf-8'))
grid=np.load(ROOT/'terrain.npz'); xs=grid['x']; ys=grid['y']; raw=grid['elevation'].copy()
# ponytail: a 3x3 display filter reduces raster steps; original 5 m elevations are retained in terrain.npz.
p=np.pad(raw,1,mode='edge')
z=sum(p[j:j+raw.shape[0],i:i+raw.shape[1]] for i in range(3) for j in range(3))/9
def height(x,y):
    u=np.clip((np.asarray(x)-xs[0])/5,0,len(xs)-1.00001)
    v=np.clip((ys[0]-np.asarray(y))/5,0,len(ys)-1.00001)
    a=u.astype(int); b=v.astype(int); fx=u-a; fy=v-b
    return z[b,a]*(1-fx)*(1-fy)+z[b,a+1]*fx*(1-fy)+z[b+1,a]*(1-fx)*fy+z[b+1,a+1]*fx*fy

def material(name,color,roughness=.8):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
    m.node_tree.nodes.clear(); bs=m.node_tree.nodes.new('ShaderNodeBsdfPrincipled'); bs.name='Principled BSDF'; out=m.node_tree.nodes.new('ShaderNodeOutputMaterial'); m.node_tree.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    bs.inputs['Base Color'].default_value=(*color,1); bs.inputs['Roughness'].default_value=roughness
    return m
mats={
 'wall':material('Campus / footprint and height or levels recorded',(.78,.79,.72)),
 'estimate':material('Campus / estimated height',(.78,.58,.33)),
 'context':material('Surrounding buildings',(.48,.54,.52)),
 'roof':material('Roof / neutral massing finish',(.52,.56,.54)),
 'roof_estimate':material('Roof / estimated height',(.65,.49,.29)),
 'road':material('Roads',(.27,.31,.31)),
 'path':material('Footpaths and steps',(.68,.62,.49)),
 'water':material('Mapped water',(.095,.34,.39),.28),
 'pitch':material('Sports pitches',(.25,.43,.30)),
 'track':material('Running tracks',(.52,.28,.19)),
 'base':material('Map plinth',(.035,.075,.085)),
 'ink':material('Labels',(.79,.85,.80)),
}
collections={}
for name in ['01 Terrain','02 Campus buildings','03 Context buildings','04 Roads and paths','05 Water and sport','06 Presentation']:
    c=bpy.data.collections.new(name); scene.collection.children.link(c); collections[name]=c
def mesh(name,verts,faces,mat,group):
    m=bpy.data.meshes.new(name); m.from_pydata(verts,[],faces); m.update()
    o=bpy.data.objects.new(name,m); collections[group].objects.link(o); o.data.materials.append(mat); return o
def move(o,group):
    for c in list(o.users_collection): c.objects.unlink(o)
    collections[group].objects.link(o)
def cube(name,loc,scale,mat,group='06 Presentation'):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object; o.name=name; o.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(mat); move(o,group); return o

terrainmat=material('Topographic terrain',(.23,.36,.23))
nt=terrainmat.node_tree; attr=nt.nodes.new('ShaderNodeVertexColor'); attr.layer_name='Elevation tint'
nt.links.new(attr.outputs['Color'],nt.nodes.get('Principled BSDF').inputs['Base Color'])
xx,yy=np.meshgrid(xs,ys); verts=np.column_stack((xx.ravel(),yy.ravel(),z.ravel())).tolist()
ny,nx=z.shape
faces=[(r*nx+c,(r+1)*nx+c,(r+1)*nx+c+1,r*nx+c+1) for r in range(ny-1) for c in range(nx-1)]
terrain=mesh('CUHK | 5 m DTM | HK1980 grid',verts,faces,terrainmat,'01 Terrain')
color=terrain.data.color_attributes.new(name='Elevation tint',type='FLOAT_COLOR',domain='POINT')
dzdy,dzdx=np.gradient(z,5); slope=np.sqrt(dzdx**2+dzdy**2).ravel()
h=z.ravel(); t=np.clip(h/260,0,1); colors=np.empty((len(h),4),np.float32)
for i,(lo,hi) in enumerate(zip((.27,.43,.31),(.46,.49,.34))): colors[:,i]=lo+(hi-lo)*t
colors[:,:3]*=(1-.1*np.clip(slope[:,None],0,1)); colors[:,3]=1
color.data.foreach_set('color',colors.ravel())
for p in terrain.data.polygons: p.use_smooth=True
terrain['source']='Hong Kong Lands Department 5 m DTM; +/-5 m published accuracy; 3x3 display smoothing'
terrain['horizontal_crs']='EPSG:2326'; terrain['vertical_datum']='Hong Kong Principal Datum'; terrain['origin_easting']=data['origin_hk1980'][0]; terrain['origin_northing']=data['origin_hk1980'][1]
edge=[]
for r,c in [(0,c) for c in range(nx)]+[(r,nx-1) for r in range(1,ny)]+[(ny-1,c) for c in range(nx-2,-1,-1)]+[(r,0) for r in range(ny-2,0,-1)]: edge.append((float(xs[c]),float(ys[r]),float(z[r,c])))
count=len(edge); sideverts=edge+[(x,y,-30) for x,y,_ in edge]
mesh('Terrain cut edge',sideverts,[(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)],mats['base'],'01 Terrain')
cube('Geographic model base',(0,0,-40),(2400,2400,20),mats['base'],'01 Terrain')
cube('Title panel',(0,-1330,-42),(2400,250,16),mats['base'])

stats={'campus':0,'context':0,'height_tag':0,'levels':0,'estimated':0,'roads':0,'water_sport':0}
inventory=[]
for f in features:
    tags=f['tags']; kind=f['kind']; name=tags.get('name:en',tags.get('name',f'{kind} {f["id"]}'))
    if kind=='building':
        source='estimated'; h=None
        def number(v):
            match=re.search(r'\d+(?:\.\d+)?',str(v)); return float(match.group()) if match else None
        if 'height' in tags: h=number(tags['height']); source='height_tag'
        if h is None and 'building:levels' in tags:
            levels=number(tags['building:levels'])
            if levels is not None: h=levels*3.3; source='levels'
        if h is None:
            # ponytail: type-based massing only; replace with surveyed/elevation data for architectural reconstruction.
            h={'dormitory':22,'university':16,'school':16,'apartments':24,'residential':12,'house':8,'detached':8,'roof':4,'shed':3,'garage':3,'garages':3,'industrial':10,'hospital':30,'hotel':40,'service':4}.get(tags.get('building'),12)
            source='estimated'
        group='02 Campus buildings' if f['campus'] else '03 Context buildings'
        wall=mats['context'] if not f['campus'] else mats['estimate'] if source=='estimated' else mats['wall']
        allxy=np.array([xy for part in f['parts'] for ring in part['rings'] for xy in ring])
        ground=float(np.percentile(height(allxy[:,0],allxy[:,1]),25))
        min_height=number(tags.get('min_height',0)) or 0
        for index,part in enumerate(f['parts']):
            vs=[(x,y,ground+h) for x,y in part['vertices']]; fs=[tuple(face) for face in part['faces']]
            roofcount=len(fs)
            # Bottom cap and wall rings preserve courtyards and concave footprints.
            k=len(vs); vs.extend((x,y,ground+min_height-.4) for x,y in part['vertices']); fs.extend(tuple(k+i for i in reversed(face)) for face in part['faces'])
            for ring in part['rings']:
                n=len(ring); k=len(vs)
                vs.extend((x,y,ground+min_height-.4) for x,y in ring); vs.extend((x,y,ground+h) for x,y in ring)
                fs.extend((k+i,k+(i+1)%n,k+(i+1)%n+n,k+i+n) for i in range(n))
            o=mesh(f'{name} | OSM {f["id"]}' + (f' part {index+1}' if index else ''),vs,fs,wall,group)
            o.data.materials.append(mats['roof_estimate'] if f['campus'] and source=='estimated' else mats['roof'])
            for poly in o.data.polygons[:roofcount]: poly.material_index=1
            bm=bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.00001); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(o.data); bm.free()
            for key,value in dict(osm_id=str(f['id']),height_m=h,height_source=source,base_elevation_hkpd_m=ground,footprint_source='OpenStreetMap',name_zh=tags.get('name:zh',''),osm_tags=json.dumps(tags,ensure_ascii=False)).items(): o[key]=value
        stats['campus' if f['campus'] else 'context']+=1
        if f['campus']: stats[source]+=1
        inventory.append(dict(osm_id=f['id'],name=name,campus=f['campus'],height_m=h,height_source=source,base_elevation_m=ground))
    else:
        if kind=='road':
            pedestrian=tags.get('highway') in ('footway','path','steps','pedestrian','cycleway'); mat=mats['path' if pedestrian else 'road']; group='04 Roads and paths'; stats['roads']+=1
        else:
            mat=mats['water' if kind in ('water','sea') or tags.get('leisure')=='swimming_pool' else 'track' if tags.get('leisure')=='track' else 'pitch']; group='05 Water and sport'; stats['water_sport']+=1
        for part in f['parts']:
            xy=np.array(part['vertices']); zz=np.zeros(len(xy)) if kind=='sea' else height(xy[:,0],xy[:,1])
            # Draped surfaces keep paths connected to steep hillside terrain.
            offset=(.8+.002*(f['id']%101)) if kind=='road' else 1.3 if tags.get('leisure')=='track' else 1.5 if tags.get('leisure')=='swimming_pool' else 1.0
            o=mesh(name,np.column_stack((xy,zz+offset)).tolist(),part['faces'],mat,group)
            o['osm_id']=str(f['id'])

def text(name,body,loc,size,mat=mats['ink']):
    c=bpy.data.curves.new(name,'FONT'); c.body=body; c.size=size; c.extrude=.02
    o=bpy.data.objects.new(name,c); collections['06 Presentation'].objects.link(o); o.location=loc; c.materials.append(mat); return o
text('Title','CUHK  /  CAMPUS TOPOGRAPHY',(-1120,-1300,-32),57)
text('Subtitle','5 m terrain  +  mapped building footprints  |  1:1 metric scene',(-1115,-1360,-32),25)
text('Source credit','Terrain: HKSAR Lands Department  |  Buildings / roads: OpenStreetMap contributors (ODbL)',(-1115,-1410,-32),20)
text('Legend','OCHRE: ESTIMATED HEIGHT   /   IVORY: HEIGHT OR STOREYS RECORDED',(-1115,-1245,-32),19)
# Scale bar with true 100 m increments.
for i in range(5): cube('Scale bar / 100 m',(-950+100*i,1100,285),(100,15,2),mats['ink'] if i%2==0 else mats['base'])
text('Scale start','0',(-995,1130,286),27)
text('Scale end','500 m',(-535,1130,286),27)
mesh('North arrow',[(1060,1110,285),(1035,1040,285),(1060,1055,285),(1085,1040,285)],[(0,1,2),(0,2,3)],mats['ink'],'06 Presentation')
text('North','N',(1043,1130,285),40)

def camera(name,loc,target,scale):
    bpy.ops.object.camera_add(location=loc); o=bpy.context.object; o.name=name; o.rotation_euler=(Vector(target)-o.location).to_track_quat('-Z','Y').to_euler(); o.data.type='ORTHO'; o.data.ortho_scale=scale; o.data.clip_end=15000; move(o,'06 Presentation'); return o
cam=camera('Camera / southeast overview',(2550,-3300,2900),(0,-100,60),3700)
top=camera('Camera / north-up plan',(0,-70,5000),(0,-70,0),2900); top.rotation_euler=(0,0,0)
scene.camera=cam
bpy.ops.object.light_add(type='SUN',location=(0,0,2000)); sun=bpy.context.object; sun.name='Sun / northwest'; sun.rotation_euler=(.45,-.55,-.5); sun.data.energy=2.5; sun.data.angle=.15; move(sun,'06 Presentation')
scene.world.color=(.25,.25,.25); scene.world.use_nodes=True
background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND'); background.inputs[0].default_value=(.34,.43,.50,1); background.inputs[1].default_value=.6
scene.render.engine='CYCLES'; scene.cycles.samples=48; scene.cycles.use_denoising=True
scene.render.resolution_x=1800; scene.render.resolution_y=1650; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene['README']='Geographic massing reconstruction. See README.md and building_inventory.json. Ochre walls indicate estimated heights. No reconstructed facades. Original terrain retained in terrain.npz.'
scene['geographic_origin_hk1980']=str(data['origin_hk1980']); scene['OSM_snapshot']=data['osm_timestamp']
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.clip_end=15000; area.spaces.active.region_3d.view_distance=3300; area.spaces.active.region_3d.view_location=(0,0,80)
            area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion(); area.spaces.active.shading.type='MATERIAL'
bpy.ops.object.select_all(action='DESELECT'); terrain.select_set(True); bpy.context.view_layer.objects.active=terrain
assert stats['campus']>150 and len(terrain.data.vertices)>200000
assert all(0<b['height_m']<500 for b in inventory)
(ROOT/'building_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'stats.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
print('MODEL_STATS',stats,flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_terrain_buildings.blend'))
scene.render.filepath=str(ROOT/'CUHK_overview.png'); bpy.ops.render.render(write_still=True)
scene.camera=top; scene.render.resolution_x=1600; scene.render.resolution_y=1800
scene.render.filepath=str(ROOT/'CUHK_topographic_plan.png'); bpy.ops.render.render(write_still=True)
print('DONE',flush=True)
