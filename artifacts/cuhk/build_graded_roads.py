"""Assemble graded roads and finer terrain in the existing labelled campus."""
import bpy,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from prepare_road_grading import load_network,height_sampler,junction_display_offsets

def mesh_object(name,verts,faces,col,material):
    mesh=bpy.data.meshes.new(name);mesh.vertices.add(len(verts));mesh.vertices.foreach_set('co',np.asarray(verts,dtype=np.float32).ravel())
    f=np.asarray(faces,dtype=np.int32);mesh.loops.add(f.size);mesh.loops.foreach_set('vertex_index',f.ravel());mesh.polygons.add(len(f));mesh.polygons.foreach_set('loop_start',np.arange(len(f),dtype=np.int32)*f.shape[1]);mesh.polygons.foreach_set('loop_total',np.full(len(f),f.shape[1],dtype=np.int32));mesh.update()
    ob=bpy.data.objects.new(name,mesh);col.objects.link(ob);mesh.materials.append(material);return ob

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_photo_rebuilt.blend'))
scene=bpy.context.scene
alignment={r['osm_id']:r for r in json.loads((ROOT/'building_terrain_alignment.json').read_text('utf-8'))}
architecture=set()
for col in bpy.data.collections:
    if col.name.startswith(('02 ','03 ','07 ','11 ')):
        architecture.update(o.name for o in col.all_objects)
for ob in bpy.data.objects:
    oid=str(ob.get('osm_id',''))
    if ob.name not in architecture or oid not in alignment:continue
    row=alignment[oid];dz=row['vertical_shift_m'];ob.location.z+=dz
    if 'base_elevation_hkpd_m' in ob:ob['base_elevation_hkpd_m']=row['new_base_m']
    if 'photo_roof_anchor' in ob:
        anchor=list(ob['photo_roof_anchor']);anchor[2]+=dz;ob['photo_roof_anchor']=anchor
    ob['terrain_alignment_shift_m']=dz;ob['terrain_alignment_method']=row['method']
old=bpy.data.collections['04 Roads and paths'];old.name='04 Original road surfaces / hidden';old.hide_render=True;old.hide_viewport=True
roads=bpy.data.collections.new('04 Roads and paths');scene.collection.children.link(roads)
structure=bpy.data.collections.new('14 Road slabs and edges');scene.collection.children.link(structure)
hidden=bpy.data.collections.new('12 Underground and indoor route references');scene.collection.children.link(hidden);hidden.hide_render=True;hidden.hide_viewport=True
from detail_buildings import _material
asphalt=_material('Road v3 / asphalt',(.105,.12,.125),.85);paths=_material('Road v3 / sandstone path',(.41,.40,.34),.9);stairs=_material('Road v3 / step approach',(.36,.37,.35),.88);slab=_material('Road v3 / concrete slab edge',(.26,.29,.28),.9)
network,junctions,segments=load_network();road_height=height_sampler(junctions,segments)
display_offsets=junction_display_offsets(network)
records=json.loads((ROOT/'road_mesh_v3.json').read_text('utf-8'));data=np.load(ROOT/'road_mesh_v3.npz');vertices=data['vertices'];faces=data['faces'];sv=[];sf=[];so=0
for r in records:
    v=vertices[r['vertex_start']:r['vertex_start']+r['vertex_count']];f=faces[r['face_start']:r['face_start']+r['face_count']]
    pedestrian=r['highway'] in ('footway','path','pedestrian','cycleway','track','steps')
    ob=mesh_object(r['name']+f' | OSM {r["id"]}/{r["part"]}',v,f,roads,stairs if r['highway']=='steps' else paths if pedestrian else asphalt)
    # Small, recorded display separation prevents coincident junction surfaces
    # from flickering in Cycles; this is far below source elevation accuracy.
    ob.location.z=display_offsets[r['profile_index']]
    ob['junction_display_separation_m']=ob.location.z
    for key in ('profile_index','id','part','surface_class','height_source'):ob['osm_id' if key=='id' else key]=r[key]
    ob['cross_section']='Level across each station, shared junction plane transitions.'
    # A separate slab provides a real edge below the road surface; top-surface
    # audits stay unambiguous because only the top meshes belong to collection04.
    edges=np.concatenate((f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]));ordered=np.sort(edges,axis=1);_,indices,counts=np.unique(ordered,axis=0,return_index=True,return_counts=True);boundary=edges[indices[counts==1]]
    slab_top=v.copy();slab_top[:,2]+=display_offsets[r['profile_index']]
    n=len(v);bottom=slab_top.copy();bottom[:,2]-=r['slab_thickness'];sv.extend((slab_top,bottom));sf.append((f[:,::-1]+n+so))
    a=boundary[:,0];b=boundary[:,1];sf.append(np.column_stack((a,a+n,b+n))+so);sf.append(np.column_stack((a,b+n,b))+so);so+=2*n
mesh_object('Road slabs / underside and perimeter',np.concatenate(sv),np.concatenate(sf),structure,slab)
for i,p in enumerate(network['profiles']):
    if p['surface_class'] in ('ground','elevated'):continue
    curve=bpy.data.curves.new('Hidden route','CURVE');curve.dimensions='3D';line=curve.splines.new('POLY');line.points.add(len(p['points'])-1);line.points.foreach_set('co',np.column_stack((np.asarray(p['points']),np.ones(len(p['points'])))).ravel())
    ob=bpy.data.objects.new(f'{p["surface_class"]} / OSM {p["id"]}/{p["part"]}',curve);hidden.objects.link(ob);ob['profile_index']=i;ob['osm_id']=str(p['id']);ob['part']=p['part'];ob['surface_class']=p['surface_class']

grid=np.load(ROOT/'terrain_roads_graded_1m.npz');xs,ys,z=grid['x'],grid['y'],grid['elevation'];ny,nx=z.shape
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o);mat=terrain.data.materials[0]
xx,yy=np.meshgrid(xs,ys);co=np.column_stack((xx.ravel(),yy.ravel(),z.ravel())).astype(np.float32)
a=(np.arange(ny-1,dtype=np.int32)[:,None]*nx+np.arange(nx-1,dtype=np.int32)[None]).ravel();tri=np.empty((2*len(a),3),dtype=np.int32);tri[0::2]=np.column_stack((a,a+nx,a+nx+1));tri[1::2]=np.column_stack((a,a+nx+1,a+1))
fresh=mesh_object('Graded terrain / 1m display sampling',co,tri,bpy.data.collections['01 Terrain'],mat);oldmesh=terrain.data;terrain.data=fresh.data;bpy.data.objects.remove(fresh,do_unlink=True)
terrain.data.polygons.foreach_set('use_smooth',np.ones(len(tri),dtype=bool));terrain['display_grid_path']=str(ROOT/'terrain_roads_graded_1m.npz');terrain['road_refinement']='Official 0.5m DTM resampled at 1m with existing site pads and local road cut/fill shoulders.'
terrain['source']='CEDD 2020 LiDAR-derived 0.5m DTM, resampled to a 1m display grid and locally graded.'
terrain.name='CUHK | 1 m graded display terrain | HK1980 grid'
terrain['source_nodata_note']='Original 5m terrain retained where the CEDD DTM has NoData, including sea. Source mask in terrain_survey_1m.npz.'
del xx,yy,co,a,tri,sv,sf

def ground(x,y):
    u=np.clip(np.asarray(x)-xs[0],0,nx-1.000001);v=np.clip(ys[0]-np.asarray(y),0,ny-1.000001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
edge=bpy.data.objects.get('Terrain cut edge')
if edge:
    coords=np.empty(len(edge.data.vertices)*3,dtype=np.float32);edge.data.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3);top=coords[:,2]>-29
    coords[top,2]=ground(coords[top,0],coords[top,1]);edge.data.vertices.foreach_set('co',coords.ravel());edge.data.update()
# Close residual sub-metre foundation gaps after local shoulder grading. These
# short plinths do not replace missing lower floors or span road underpasses.
plinth_v=[];plinth_f=[]
features=json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']
for feature in features:
    if feature['kind']!='building' or str(feature['id']) not in alignment:continue
    geom=feature['geometry'];polys=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates'] if geom['type']=='MultiPolygon' else []
    top=alignment[str(feature['id'])]['new_base_m']-.35
    for poly in polys:
        ring=np.asarray(poly[0])
        for a,b in zip(ring[:-1],ring[1:]):
            steps=max(1,int(np.ceil(np.linalg.norm(b-a)/1.5)))
            for t in range(steps):
                p=a+(b-a)*t/steps;q=a+(b-a)*(t+1)/steps;za=float(ground(*p));zb=float(ground(*q))
                if max(top-za,top-zb)<.05 or max(top-za,top-zb)>3:continue
                i=len(plinth_v);plinth_v.extend(((p[0],p[1],top),(q[0],q[1],top),(q[0],q[1],min(top,zb)-.05),(p[0],p[1],min(top,za)-.05)));plinth_f.append((i,i+1,i+2,i+3))
if plinth_v:
    plinth=mesh_object('Local foundation plinths / illustrative',plinth_v,plinth_f,structure,slab);plinth['maximum_supported_gap_m']=3
def furniture_height(x,y,oid):
    hz=road_height(x,y,oid) if str(oid) in segments else ground(x,y)
    return hz-.8-.002*(int(oid)%101)
oldgrid=np.load(ROOT/'terrain_refined_display.npz');oldz=oldgrid['elevation']
def sport_ground(x,y):
    u=np.clip((np.asarray(x)-oldgrid['x'][0])/5,0,oldz.shape[1]-1.000001);v=np.clip((oldgrid['y'][0]-np.asarray(y))/5,0,oldz.shape[0]-1.000001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,oldz[b,a]*(1-fy)+oldz[b+1,a]*(fy-fx)+oldz[b+1,a+1]*fx,oldz[b,a]*(1-fx)+oldz[b,a+1]*(fx-fy)+oldz[b+1,a+1]*fy)
from detail_site import apply_site_details
clearance={}
for j in network['junctions']:
    if j['degree']<3:continue
    radius=max(r['width'] for r in j['incident_roads'])/2+1
    for oid in j['osm_way_ids']:clearance.setdefault(str(oid),[]).append((j['xyz'][:2],radius))
site=apply_site_details(height_fn=sport_ground,road_height_fn=furniture_height,junction_clearance=clearance)
for ob in bpy.data.collections['09 Mapped vegetation / illustrative crowns'].objects:ob.location.z=float(ground(ob.location.x,ob.location.y))-.8
scene['road_network_path']=str(ROOT/'road_network_v3.json');scene['road_grading_report']=str(ROOT/'ROAD_GRADING.md');scene['road_revision']='Corrected road elevations, level cross sections, common junction planes, 1m display terrain with cut/fill shoulder blending.'
scene['terrain_quality_note']='Survey-derived terrain with explicitly modelled architecture pads and local cut/fill. Does not represent measured earthworks or certified bridge clearance.'
scene['README']='CUHK graded-road revision: official 0.5m CEDD DTM resampled to 1m display terrain, road profiles guided by official XYZ paths, local cut/fill, aligned architectural bases. Source architecture/height assumptions remain; see ROAD_GRADING.md.'
if 'Subtitle' in bpy.data.objects:bpy.data.objects['Subtitle'].data.body='1 m display terrain from CEDD 0.5 m DTM  |  1:1 metric scene'
if 'Source credit' in bpy.data.objects:bpy.data.objects['Source credit'].data.body='Terrain: HKSAR CEDD  |  Road references: LandsD  |  Footprints: OpenStreetMap contributors'
scene.camera=bpy.data.objects['Camera / core architectural detail'];scene.render.resolution_x=3600;scene.render.resolution_y=2700;scene.render.resolution_percentage=100
from building_labels import apply_building_labels
bpy.context.view_layer.update();apply_building_labels(scene.camera,mode='closeup')
scene.cycles.samples=96;scene.cycles.use_denoising=True
scene.render.filepath=str(ROOT/'CUHK_roads_graded_preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_roads_graded.blend'))
print('GRADED_BLEND_READY',len(records),len(terrain.data.vertices),flush=True)
