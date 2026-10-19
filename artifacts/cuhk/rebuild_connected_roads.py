"""Rebuild rendered road surfaces from genuine OSM-node topology; regrade roadbeds."""
import bpy,json,sys,math
from pathlib import Path
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
network=json.loads((ROOT/'road_network_v2.json').read_text('utf-8'))
profiles=network['profiles'];by_id={};junctions={}
for i,p in enumerate(profiles):by_id.setdefault(str(p['id']),[]).append(i)
for j in network['junctions']:
    q=np.array(j['xyz']);A=[];B=[]
    for pi in j['profile_indices']:
        p=np.array(profiles[pi]['points']);d=np.linalg.norm(p[:,:2]-q[:2],axis=1)
        use=np.flatnonzero((d>2)&(d<8))
        if len(use):A.extend((p[use,:2]-q[:2]).tolist());B.extend((p[use,2]-q[2]).tolist())
    slope=np.linalg.lstsq(np.vstack((np.asarray(A).reshape(-1,2),np.eye(2)*2)),np.r_[B,0,0],rcond=None)[0]
    r=max(x['width'] for x in j['incident_roads'])/2+.5
    for oid in j['osm_way_ids']:junctions.setdefault(str(oid),[]).append((q,r,slope))
segments={}
for oid,indices in by_id.items():
    a=np.concatenate([np.array(profiles[i]['points'])[:-1] for i in indices]);b=np.concatenate([np.array(profiles[i]['points'])[1:] for i in indices]);segments[oid]=(a,b)
def road_height(x,y,oid):
    xx,yy=np.broadcast_arrays(np.asarray(x),np.asarray(y));shape=xx.shape;q=np.column_stack((xx.ravel(),yy.ravel()));out=[]
    a,b=segments[str(oid)];v=b[:,:2]-a[:,:2];den=np.maximum(np.sum(v*v,axis=1),1e-10)
    for start in range(0,len(q),192):
        pts=q[start:start+192];t=np.clip(np.sum((pts[:,None,:]-a[None,:,:2])*v[None,:,:],axis=2)/den,0,1)
        dist=np.sum((pts[:,None,:]-a[None,:,:2]-t[:,:,None]*v[None,:,:])**2,axis=2);k=np.argmin(dist,axis=1);ii=np.arange(len(pts));tt=t[ii,k]
        z=a[k,2]*(1-tt)+b[k,2]*tt
        js=junctions.get(str(oid),[])
        if js:
            centers=np.array([j[0][:2] for j in js]);dd=np.linalg.norm(pts[:,None,:]-centers,axis=2);nearest=np.argmin(dd,axis=1)
            for n in np.unique(nearest):
                pick=np.flatnonzero(nearest==n);center,r,slope=js[n];d=dd[pick,n]
                weight=np.clip((r+5-d)/5,0,1);weight=weight*weight*(3-2*weight)
                plane=center[2]+(pts[pick]-center[:2])@slope
                z[pick]=z[pick]*(1-weight)+plane*weight
        out.extend(z.tolist())
    return np.asarray(out).reshape(shape)+.15

bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_photo_rebuilt.blend'))
scene=bpy.context.scene
old=bpy.data.collections['04 Roads and paths']
old.name='04 Previous road surfaces / hidden';old.hide_render=True;old.hide_viewport=True
group=bpy.data.collections.new('04 Roads and paths');scene.collection.children.link(group)
hidden=bpy.data.collections.new('12 Underground and indoor route references');scene.collection.children.link(hidden);hidden.hide_render=True;hidden.hide_viewport=True
from detail_buildings import _material
asphalt=_material('Road v2 / asphalt',(.105,.125,.128),.86)
pathmat=_material('Road v2 / footway',(.42,.405,.325),.88)
stairs=_material('Road v2 / stepped routes',(.37,.37,.33),.85)
grid=np.load(ROOT/'terrain_roads_smoothed.npz');xs,ys=grid['x'],grid['y'];original=grid['elevation'].astype(float);z=original.copy();ny,nx=z.shape
limits=np.full(z.shape,np.inf);ground_faces=[];mesh_records=[]
for i,p in enumerate(profiles):
    xyz=np.asarray(p['points']);xy=xyz[:,:2];w=p['width'];oid=str(p['id']);kind=p['surface_class']
    if len(xy)<2:continue
    d=np.diff(xy,axis=0);d/=np.maximum(np.linalg.norm(d,axis=1)[:,None],1e-10)
    nn=np.column_stack((-d[:,1],d[:,0]));normals=np.empty_like(xy);normals[0]=nn[0];normals[-1]=nn[-1]
    for k in range(1,len(xy)-1):
        n=nn[k-1]+nn[k];n/=max(np.linalg.norm(n),1e-10);normals[k]=n/max(.65,float(n@nn[k]))
    points=np.stack((xy-normals*w/2,xy,xy+normals*w/2),axis=1).reshape(-1,2)
    heights=road_height(points[:,0],points[:,1],oid);vertices=np.column_stack((points,heights)).tolist();faces=[]
    for k in range(len(xy)-1):
        a=k*3;b=(k+1)*3
        faces.extend(((a,b,b+1),(a,b+1,a+1),(a+1,b+1,b+2),(a+1,b+2,a+2)))
    # Round end caps join retained source approaches without inventing centreline links.
    for at in (0,len(xy)-1):
        center=xy[at];angles=np.linspace(0,2*math.pi,17)[:-1];ring=center+np.column_stack((np.cos(angles),np.sin(angles)))*w/2
        zz=road_height(ring[:,0],ring[:,1],oid);base=len(vertices);vertices.extend(np.column_stack((ring,zz)).tolist())
        faces.extend((at*3+1,base+k,base+(k+1)%16) for k in range(16))
    mesh=bpy.data.meshes.new(f'Connected road {oid}/{p["part"]}');mesh.from_pydata(vertices,[],faces);mesh.update()
    pedestrian=p['highway'] in ('footway','path','steps','pedestrian','cycleway','corridor','track')
    mesh.materials.append(stairs if p['highway']=='steps' else pathmat if pedestrian else asphalt)
    ob=bpy.data.objects.new(p['tags'].get('name:en',p['tags'].get('name',p['highway']))+f' | OSM {oid}/{p["part"]}',mesh)
    visible=kind in ('ground','elevated')
    (group if visible else hidden).objects.link(ob)
    for key,value in {'osm_id':oid,'surface_class':kind,'source_layer':p['layer'],'topology':'Original OSM shared node IDs, including genuine bridge approach connections','height_source':p['height_source'],'uniform_surface_offset_m':.15}.items():ob[key]=value
    for poly in mesh.polygons:poly.use_smooth=False
    mesh_records.append({'id':oid,'part':p['part'],'surface_class':kind,'vertices':len(vertices),'triangles':len(faces),'rendered':visible})
    if kind=='ground':ground_faces.append(np.asarray(vertices)[np.asarray(faces)])
print('ROAD_GEOMETRY_READY',len(mesh_records),flush=True)

# Conservative cell constraints keep rendered ground-road triangles above the
# displayed terrain. Bridge decks and underground/indoor paths never cut terrain.
# The 5m source grid remains a display approximation; new survey data is separate.
tris=np.concatenate(ground_faces);lo=tris[:,:,:2].min(axis=1);hi=tris[:,:,:2].max(axis=1);lowz=tris[:,:,2].min(axis=1)-.16
c0=np.maximum(0,np.floor((lo[:,0]-xs[0])/5).astype(int));c1=np.minimum(nx-2,np.floor((hi[:,0]-xs[0])/5).astype(int))
r0=np.maximum(0,np.floor((ys[0]-hi[:,1])/5).astype(int));r1=np.minimum(ny-2,np.floor((ys[0]-lo[:,1])/5).astype(int))
for dr in range(int(np.max(r1-r0))+1):
    for dc in range(int(np.max(c1-c0))+1):
        rr=r0+dr;cc=c0+dc;ok=(rr<=r1)&(cc<=c1)&(rr>=0)&(cc>=0)
        for ar,ac in ((0,0),(1,0),(0,1),(1,1)):np.minimum.at(limits,(rr[ok]+ar,cc[ok]+ac),lowz[ok])
cut=np.maximum(0,original-limits);cut[~np.isfinite(cut)]=0
# Spread only the edges of the cut as shoulders; the road-cell constraint remains exact.
shoulder=cut.copy()
for scale in (.52,.27):
    padded=np.pad(shoulder,1,mode='edge')
    nearby=np.maximum.reduce([padded[j:j+ny,k:k+nx] for j in range(3) for k in range(3)])*scale
    shoulder=np.maximum(shoulder,nearby)
z=original-shoulder
np.savez_compressed(ROOT/'terrain_connected_roads.npz',elevation=z,x=xs,y=ys)
terrain=next(o for o in bpy.data.objects if 'horizontal_crs' in o)
co=np.empty(len(terrain.data.vertices)*3,dtype=np.float32);terrain.data.vertices.foreach_get('co',co);co=co.reshape(-1,3);co[:,2]=z.ravel();terrain.data.vertices.foreach_set('co',co.ravel());terrain.data.update()
terrain['road_refinement']='Ground-road conservative cell grading; original OSM connected-node road profiles; elevated/indoor/tunnel routes excluded from new grading.'
terrain['display_grid_path']=str(ROOT/'terrain_connected_roads.npz')
def ground(x,y):
    u=np.clip((np.asarray(x)-xs[0])/5,0,nx-1.000001);v=np.clip((ys[0]-np.asarray(y))/5,0,ny-1.000001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
# Keep sports fixed while regenerating road furniture with the new shared surface height.
def furniture_height(x,y,oid):
    if str(oid) not in segments:return ground(x,y)-.8-.002*(int(oid)%101)
    return road_height(x,y,oid)-.8-.002*(int(oid)%101)
from detail_site import apply_site_details
oldz=np.load(ROOT/'terrain_refined_display.npz')['elevation']
def sport_ground(x,y):
    u=np.clip((np.asarray(x)-xs[0])/5,0,nx-1.000001);v=np.clip((ys[0]-np.asarray(y))/5,0,ny-1.000001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,oldz[b,a]*(1-fy)+oldz[b+1,a]*(fy-fx)+oldz[b+1,a+1]*fx,oldz[b,a]*(1-fx)+oldz[b,a+1]*(fx-fy)+oldz[b+1,a+1]*fy)
site=apply_site_details(height_fn=sport_ground,road_height_fn=furniture_height)
for o in bpy.data.collections['09 Mapped vegetation / illustrative crowns'].objects:o.location.z=float(ground(o.location.x,o.location.y))-.8
# Check the actual surface sampler on every original connected source node.
gaps=[]
for j in network['junctions']:
    q=j['xyz'];heights=[float(road_height(q[0],q[1],oid)) for oid in j['osm_way_ids']];gaps.append(max(heights)-min(heights))
assert max(gaps)<1e-5,max(gaps)
stats={'network':network['stats'],'rendered_road_objects':sum(r['rendered'] for r in mesh_records),'retained_hidden_routes':sum(not r['rendered'] for r in mesh_records),'actual_surface_sampler_max_junction_gap_m':max(gaps),'terrain_cells_lowered':int(np.sum(shoulder>.001)),'max_additional_terrain_cut_m':float(shoulder.max()),'mean_cut_on_changed_cells_m':float(shoulder[shoulder>.001].mean()),'road_objects':mesh_records,'site':site,'limitation':'Existing schematic elevations remain; this fixes shared-node continuity and ground-surface burial. Ground grading retains the existing 5m display grid. New official 0.5m survey rasters and 3D network are separate data, not silently substituted.'}
(ROOT/'connected_roads_report.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
scene['road_topology_repair']=json.dumps({k:v for k,v in stats.items() if k not in ('road_objects','site')},ensure_ascii=False)
scene.cycles.samples=96;scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences;prefs.compute_device_type='OPTIX';prefs.get_devices()
for d in prefs.devices:d.use=d.type=='OPTIX'
scene.cycles.device='GPU';scene.camera=bpy.data.objects['Camera / core architectural detail'];scene.render.resolution_x=3600;scene.render.resolution_y=2700
labelgroup=bpy.data.collections['10 Building labels / OSM names'];labelgroup.hide_render=True
scene.render.filepath=str(ROOT/'CUHK_connected_roads_preview.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_connected_roads.blend'))
bpy.ops.render.render(write_still=True)
labelgroup.hide_render=False;scene.render.filepath=str(ROOT/'CUHK_connected_roads_labeled.png')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_connected_roads.blend'))
bpy.ops.render.render(write_still=True)
print('CONNECTED_ROADS_COMPLETE',max(gaps),flush=True)
