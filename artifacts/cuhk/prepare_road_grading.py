"""Road cross sections and local cut/fill shoulders on the 1m display terrain."""
import json,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent

def load_network():
    network=json.loads((ROOT/'road_network_v3.json').read_text('utf-8'))
    profiles=network['profiles'];junctions={};segments={}
    for j in network['junctions']:
        q=np.array(j['xyz']);aa=[];bb=[]
        for pi in j['profile_indices']:
            p=np.array(profiles[pi]['points']);d=np.linalg.norm(p[:,:2]-q[:2],axis=1)
            use=np.flatnonzero((d>4)&(d<13))
            if len(use):aa.extend(p[use,:2]-q[:2]);bb.extend(p[use,2]-q[2])
        slope=np.linalg.lstsq(np.vstack((np.asarray(aa).reshape(-1,2),np.eye(2)*4)),np.r_[bb,0,0],rcond=None)[0]
        vehicular=any(profiles[pi]['highway'] not in ('footway','path','pedestrian','steps','corridor') for pi in j['profile_indices'])
        cap=.18 if vehicular else .38
        slope*=min(1,cap/max(np.linalg.norm(slope),1e-9))
        radius=max(p['width'] for p in j['incident_roads'])/2+1
        for oid in j['osm_way_ids']:junctions.setdefault(str(oid),[]).append((q,radius,slope))
    for p in profiles:
        xy=np.asarray(p['points']);segments.setdefault(str(p['id']),[]).append(xy)
    segments={oid:(np.concatenate([p[:-1] for p in pp]),np.concatenate([p[1:] for p in pp])) for oid,pp in segments.items()}
    return network,junctions,segments

def height_sampler(junctions,segments):
    def sample(x,y,oid):
        xx,yy=np.broadcast_arrays(np.asarray(x),np.asarray(y));shape=xx.shape;pts=np.column_stack((xx.ravel(),yy.ravel()));out=[]
        a,b=segments[str(oid)];v=b[:,:2]-a[:,:2];den=np.maximum(np.sum(v*v,axis=1),1e-10)
        for begin in range(0,len(pts),128):
            q=pts[begin:begin+128];t=np.clip(np.sum((q[:,None]-a[None,:,:2])*v[None],axis=2)/den,0,1)
            d=np.sum((q[:,None]-a[None,:,:2]-t[:,:,None]*v[None])**2,axis=2);ii=np.arange(len(q));k=np.argmin(d,axis=1)
            z=a[k,2]+t[ii,k]*(b[k,2]-a[k,2])
            js=junctions.get(str(oid),[])
            if js:
                dd=np.linalg.norm(q[:,None]-np.array([j[0][:2] for j in js])[None],axis=2);near=np.argmin(dd,axis=1)
                for n in np.unique(near):
                    pick=np.flatnonzero(near==n);center,r,slope=js[n];w=np.clip((r+7-dd[pick,n])/7,0,1);w=w*w*(3-2*w)
                    z[pick]=z[pick]*(1-w)+(center[2]+(q[pick]-center[:2])@slope)*w
            out.extend(z+.15)
        return np.asarray(out).reshape(shape)
    return sample

def junction_display_offsets(network):
    """Millimetre render offsets; adjacent source-connected roads must differ."""
    visible={i for i,p in enumerate(network['profiles']) if p['surface_class'] in ('ground','elevated')}
    neighbors={i:set() for i in visible}
    for junction in network['junctions']:
        incident=visible.intersection(junction['profile_indices'])
        for i in incident:neighbors[i].update(incident-{i})
    colors={}
    for i in sorted(visible,key=lambda i:(-len(neighbors[i]),i)):
        used={colors[j] for j in neighbors[i] if j in colors};color=0
        while color in used:color+=1
        colors[i]=color
    offsets={i:.0015*(color+1) for i,color in colors.items()}
    assert all(abs(offsets[i]-offsets[j])>=.00149 for i in neighbors for j in neighbors[i])
    return offsets

def road_surface(p,sampler,junctions):
    """Triangulate one buffered footprint; insert its actual source stations."""
    import shapely
    from shapely.geometry import LineString
    from shapely.ops import split
    from scipy.spatial import Delaunay
    # Blender stores mesh coordinates in float32. Triangulate those same
    # representable coordinates, so conversion cannot flip needle triangles.
    xy=np.asarray(p['points'],dtype=np.float32)[:,:2].astype(float);oid=str(p['id']);width=float(p['width'])
    xy=xy[np.r_[True,np.linalg.norm(np.diff(xy,axis=0),axis=1)>1e-9]]
    assert len(xy)>1 and width>0,(oid,'empty road')
    closed=np.linalg.norm(xy[0]-xy[-1])<1e-7
    footprint=LineString(xy).buffer(width/2,quad_segs=8,cap_style='round',join_style='round').simplify(.0002,preserve_topology=True).segmentize(.999)
    pieces=[footprint]
    if not closed:
        span=math.hypot(footprint.bounds[2]-footprint.bounds[0],footprint.bounds[3]-footprint.bounds[1])+width
        # Constrain each cap diameter, so a triangle cannot straddle the
        # planar half-disk and the sloping interior road surface.
        for at,other in ((0,1),(-1,-2)):
            center=xy[at];tangent=center-xy[other];normal=np.array([-tangent[1],tangent[0]]);normal*=span/np.linalg.norm(normal)
            divider=LineString([center-normal,center,center+normal])
            pieces=[part for piece in pieces for part in split(piece,divider).geoms]
    if oid in ('224754465','761180546','230089601'):
        # These three long alignments produce 118-401m needle triangles.
        # Bound their XY cell size before triangulation so the terrain's
        # conservative triangle-bbox constraint cannot excavate a broad area.
        cells=[]
        for piece in pieces:
            x0,y0,x1,y1=piece.bounds;gx=np.arange(math.floor(x0/2)*2,math.ceil(x1/2)*2,2.);gy=np.arange(math.floor(y0/2)*2,math.ceil(y1/2)*2,2.)
            shapely.prepare(piece)
            for begin in range(0,len(gy),64):
                xx,yy=np.meshgrid(gx,gy[begin:begin+64]);xx=xx.ravel();yy=yy.ravel();boxes=shapely.box(xx,yy,xx+2,yy+2)
                hits=boxes[shapely.intersects(piece,boxes)]
                parts=shapely.get_parts(shapely.intersection(piece,hits))
                cells.extend(parts[(shapely.get_type_id(parts)==3)&(shapely.area(parts)>1e-10)])
        pieces=cells
    pieces=[shapely.transform(piece,lambda a:a.astype(np.float32).astype(float)) for piece in pieces]
    rounded=[]
    for piece in pieces:
        repaired=shapely.get_parts(shapely.make_valid(piece)) if not piece.is_valid else [piece]
        rounded.extend(shapely.transform(part,lambda a:a.astype(np.float32).astype(float)) for part in repaired if part.geom_type=='Polygon' and part.area>1e-10)
    pieces=rounded
    assert all(piece.is_valid and piece.area>0 for piece in pieces),(oid,'invalid buffer')
    footprint=shapely.union_all(pieces)
    triangles=np.concatenate([shapely.get_parts(shapely.constrained_delaunay_triangles(piece)) for piece in pieces])
    stations=np.unique(xy,axis=0)
    # Partition source points among the already constrained triangles. Points
    # on a shared edge go into both adjacent triangulations, preventing cracks.
    pairs=shapely.STRtree(shapely.points(stations)).query(triangles,predicate='covers')
    groups={}
    for ti,si in pairs.T:groups.setdefault(int(ti),[]).append(int(si))
    assert len(np.unique(pairs[1]))==len(stations),(oid,'uncovered source station')
    vertices=[];faces=[];lookup={}
    for ti,triangle in enumerate(triangles):
        corners=np.asarray(triangle.exterior.coords)[:3,:2]
        points=np.unique(np.vstack((corners,stations[groups[ti]])),axis=0) if ti in groups else corners
        local=Delaunay(points).simplices if len(points)>3 else np.array([[0,1,2]])
        assert len(np.unique(local))==len(points),(oid,'local triangulation dropped a source point')
        ids=[]
        for q in points:
            key=tuple(q)
            if key not in lookup:lookup[key]=len(vertices);vertices.append(q)
            ids.append(lookup[key])
        for f in local:
            a,b,c=points[f];ab=b-a;ac=c-a;area=ab[0]*ac[1]-ab[1]*ac[0]
            if abs(area)<1e-12:continue
            if area<0:f=f[[0,2,1]]
            faces.append([ids[i] for i in f])
    vertices=np.asarray(vertices);faces=np.asarray(faces,dtype=np.int32)
    z=sampler(vertices[:,0],vertices[:,1],oid)
    # The half-disks beyond open ends are planar. They are part of the single
    # footprint, rather than overlapping full disks sampled against a bend.
    if not closed:
        for at,other in ((0,1),(-1,-2)):
            center=xy[at];outward=center-xy[other];outward/=np.linalg.norm(outward)
            delta=vertices-center
            cap=(delta@outward>=-.0002)&(np.linalg.norm(delta,axis=1)<=width/2+.0002)
            slope=np.zeros(2);js=junctions.get(oid,[])
            if js:
                j=min(js,key=lambda j:np.linalg.norm(center-j[0][:2]));q,r,plane=j
                blend=np.clip((r+7-np.linalg.norm(center-q[:2]))/7,0,1);blend=blend*blend*(3-2*blend)
                slope=plane*blend
            z[cap]=float(sampler(center[0],center[1],oid))+delta[cap]@slope
    shared=0;shared_error=0.
    used=set(np.unique(faces))
    for station in stations:assert lookup[tuple(station)] in used,(oid,'unused source station')
    for q,r,slope in junctions.get(oid,[]):
        qxy=q[:2].astype(np.float32).astype(float)
        if np.min(np.linalg.norm(xy-qxy,axis=1))>1e-7:continue
        k=lookup.get(tuple(qxy))
        assert k is not None,(oid,'missing shared junction vertex',q.tolist())
        z[k]=q[2]+.15;shared+=1
        shared_error=max(shared_error,abs(z[k]-q[2]-.15))
    verts=np.column_stack((vertices,z));t=vertices[faces]
    ab=t[:,1]-t[:,0];ac=t[:,2]-t[:,0];areas=(ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0])/2
    assert np.all(areas>0),(oid,'reversed triangle')
    area_error=abs(float(areas.sum())-footprint.area)
    assert area_error<max(1e-7,footprint.area*1e-9),(oid,'overlap or missing footprint area',area_error)
    assert len({tuple(sorted(f)) for f in faces})==len(faces),(oid,'duplicate face')
    return verts,faces,{'area_m2':float(footprint.area),'area_error_m2':area_error,'shared_vertices':shared,'shared_vertex_error_m':shared_error}

def main():
    import sys
    sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
    from scipy.ndimage import distance_transform_edt,gaussian_filter
    network,junctions,segments=load_network();sampler=height_sampler(junctions,segments)
    source=np.load(ROOT/'terrain_platforms_1m.npz');xs,ys=source['x'],source['y'];base=source['elevation'].astype(float);ny,nx=base.shape
    ground_limit=np.full(base.shape,np.inf);all_limit=ground_limit.copy()
    vv=[];ff=[];records=[];vstart=0;fstart=0;geometry_checks=[]
    for pi,p in enumerate(network['profiles']):
        if p['surface_class'] not in ('ground','elevated'):continue
        w=p['width'];oid=str(p['id'])
        verts,faces,check=road_surface(p,sampler,junctions);geometry_checks.append(check);tris=verts[faces]
        # Constrain all terrain corners of cells touched by each road triangle.
        # At 1m spacing this keeps road edges clear without 5m-wide notches.
        lo=tris[:,:,:2].min(axis=1);hi=tris[:,:,:2].max(axis=1)
        thickness=.35 if p['surface_class']=='elevated' else .14
        ceiling=tris[:,:,2].min(axis=1)-thickness-.07
        c0=np.maximum(0,np.floor(lo[:,0]-xs[0]).astype(int));c1=np.minimum(nx-2,np.floor(hi[:,0]-xs[0]).astype(int))
        r0=np.maximum(0,np.floor(ys[0]-hi[:,1]).astype(int));r1=np.minimum(ny-2,np.floor(ys[0]-lo[:,1]).astype(int))
        for dr in range(max(0,int(np.max(r1-r0)))+1):
            for dc in range(max(0,int(np.max(c1-c0)))+1):
                rr=r0+dr;cc=c0+dc;ok=(rr<=r1)&(cc<=c1)&(rr>=0)&(cc>=0)&(rr<ny-1)&(cc<nx-1)
                for ar,ac in ((0,0),(1,0),(0,1),(1,1)):
                    np.minimum.at(all_limit,(rr[ok]+ar,cc[ok]+ac),ceiling[ok])
                    if p['surface_class']=='ground':np.minimum.at(ground_limit,(rr[ok]+ar,cc[ok]+ac),ceiling[ok])
        records.append({'profile_index':pi,'id':oid,'part':p['part'],'surface_class':p['surface_class'],'highway':p['highway'],'width':w,'vertex_start':vstart,'vertex_count':len(verts),'face_start':fstart,'face_count':len(faces),'slab_thickness':thickness,'name':p['tags'].get('name:en',p['tags'].get('name',p['highway'])),'height_source':p['height_source']})
        vv.append(verts.astype(np.float32));ff.append(faces);vstart+=len(verts);fstart+=len(faces)
    fixed=np.isfinite(ground_limit)|(base>all_limit)
    target=base.copy();g=np.isfinite(ground_limit);target[g]=ground_limit[g];target=np.minimum(target,all_limit)
    delta=np.zeros_like(base);delta[fixed]=target[fixed]-base[fixed]
    dist,idx=distance_transform_edt(~fixed,return_indices=True);near=delta[tuple(idx)]
    # A broad cubic transition gives cut/fill banks a gradual return to the
    # surrounding slope, rather than a cliff at the next terrain grid cell.
    radius=np.clip(8+np.abs(near)*2.5,8,48);weight=np.clip(1-dist/radius,0,1);weight=weight*weight*(3-2*weight)
    shoulder=gaussian_filter(near*weight,sigma=1.5);terrain=base+shoulder
    terrain[fixed]=target[fixed];terrain=np.minimum(terrain,all_limit)
    assert np.isfinite(terrain).all()
    gap=[]
    for j in network['junctions']:
        q=j['xyz'];hz=[float(sampler(q[0],q[1],oid)) for oid in j['osm_way_ids']];gap.append(max(hz)-min(hz))
    assert max(gap)<1e-5,max(gap)
    np.savez_compressed(ROOT/'road_mesh_v3.npz',vertices=np.concatenate(vv),faces=np.concatenate(ff))
    np.savez_compressed(ROOT/'terrain_roads_graded_1m.npz',x=xs,y=ys,elevation=terrain.astype(np.float32))
    (ROOT/'road_mesh_v3.json').write_text(json.dumps(records,ensure_ascii=False),encoding='utf-8')
    diff=terrain-base;changed=abs(diff)>.01
    stats={'visible_road_count':len(records),'shared_junction_sampler_gap_m':max(gap),'terrain_grid_spacing_m':1,'terrain_vertices':int(terrain.size),'changed_cells':int(changed.sum()),'cut_max_m':float(-min(0,diff.min())),'fill_max_m':float(max(0,diff.max())),'mean_absolute_change_m':float(abs(diff[changed]).mean()),'source_note':'Source is official 0.5m DTM resampled at 1m, with legacy NoData fallback and existing architecture pads. Local road cut/fill is illustrative, based on source-matched road elevations; not engineering earthworks.'}
    stats['geometry']={'method':'Round buffered footprint, constrained Delaunay, explicit source stations, planar open caps','vertices':vstart,'triangles':fstart,'reversed_triangles':0,'duplicate_faces':0,'max_area_error_m2':max(c['area_error_m2'] for c in geometry_checks),'shared_vertex_instances':sum(c['shared_vertices'] for c in geometry_checks),'max_shared_vertex_error_m':max(c['shared_vertex_error_m'] for c in geometry_checks)}
    (ROOT/'road_grading_report.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
