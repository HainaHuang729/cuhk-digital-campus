"""Level the two mapped running facilities while preserving existing road beds."""
import json,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import shapely
from shapely.geometry import shape,Polygon,mapping,LineString,box
from scipy.ndimage import distance_transform_edt

features=json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']
grid=np.load(ROOT/'terrain_roads_graded_1m.npz')
xs,ys=grid['x'],grid['y'];base=grid['elevation'];out=base.copy()
survey=np.load(ROOT/'terrain_survey_1m.npz')
assert np.array_equal(xs,survey['x']) and np.array_equal(ys,survey['y'])
mesh=np.load(ROOT/'road_mesh_v3.npz');vertices,faces=mesh['vertices'],mesh['faces']
roads=json.loads((ROOT/'road_mesh_v3.json').read_text('utf-8'))
profiles=json.loads((ROOT/'road_network_v3.json').read_text('utf-8'))['profiles']
adjustment=np.load(ROOT/'sports_path_adjustment.npz') if (ROOT/'sports_path_adjustment.npz').exists() else None
facilities=[]
protected=np.zeros(base.shape,dtype=bool)
for track in [f for f in features if f['kind']=='sport' and f['tags'].get('sport')=='running']:
    centerline=shape(track['geometry'])
    assert centerline.geom_type=='LineString' and centerline.is_ring
    core=Polygon(centerline.coords)
    members=[f for f in features if f['kind']=='sport' and f['id']!=track['id'] and core.covers(shape(f['geometry']).representative_point())]
    # A closed track is a whole facility, including its infield, not a terrain-draped line.
    footprint=shapely.union_all([core.buffer(4)]+[shape(f['geometry']) for f in members]).buffer(1)
    assert footprint.is_valid
    x0,y0,x1,y1=footprint.bounds
    ci=np.flatnonzero((xs>=x0-10)&(xs<=x1+10));ri=np.flatnonzero((ys>=y0-10)&(ys<=y1+10))
    xx,yy=np.meshgrid(xs[ci],ys[ri]);distance=shapely.distance(shapely.points(xx,yy),footprint)
    inside=shapely.contains_xy(footprint,xx,yy)
    valid=inside&survey['source_valid'][np.ix_(ri,ci)]
    level=float(np.median(survey['elevation'][np.ix_(ri,ci)][valid]))
    weight=np.clip(1-distance/10,0,1);weight=weight*weight*(3-2*weight)
    localbase=base[np.ix_(ri,ci)]
    local=(localbase*(1-weight)+(level-.08)*weight).astype(np.float32)
    roadmask=np.zeros(local.shape,dtype=bool);new_limit=np.full(local.shape,np.inf);conflicts=[];nearby=[]
    localbounds=box(xs[ci[0]],ys[ri[-1]],xs[ci[-1]],ys[ri[0]])
    for road in roads:
        vv=vertices[road['vertex_start']:road['vertex_start']+road['vertex_count']]
        moved=adjustment is not None and road['id']=='475648093'
        if moved:vv=adjustment['new_vertices']
        if vv[:,0].max()<x0-11 or vv[:,0].min()>x1+11 or vv[:,1].max()<y0-11 or vv[:,1].min()>y1+11:continue
        ff=faces[road['face_start']:road['face_start']+road['face_count']]
        tris=vv[ff]
        triangle_polygons=shapely.polygons(tris[:,:,:2])
        hit=shapely.intersects(triangle_polygons,localbounds)
        if not np.any(hit):continue
        nearby.append(road['id'])
        # Match the road grader's conservative cell-corner mask. Capping at the
        # already-audited old terrain guarantees this edit cannot reduce clearance.
        for tri in tris[hit]:
            c0=max(0,int(np.floor(tri[:,0].min()-xs[ci[0]])))
            c1=min(len(ci)-2,int(np.floor(tri[:,0].max()-xs[ci[0]])))
            r0=max(0,int(np.floor(ys[ri[0]]-tri[:,1].max())))
            r1=min(len(ri)-2,int(np.floor(ys[ri[0]]-tri[:,1].min())))
            if c1>=c0 and r1>=r0:
                roadmask[r0:r1+2,c0:c1+2]=True
                if moved:
                    new_limit[r0:r1+2,c0:c1+2]=np.minimum(new_limit[r0:r1+2,c0:c1+2],float(tri[:,2].min())-road['slab_thickness']-.07)
        overlap=shapely.intersection(triangle_polygons[hit],footprint)
        areas=shapely.area(overlap);touched=areas>1e-6
        if np.any(touched):
            roadshape=shapely.union_all(triangle_polygons[hit])
            profile=profiles[road['profile_index']]
            roadline=LineString(np.asarray(profile['points'])[:,:2])
            heights=tris[hit][touched,:,2]
            conflicts.append({'road_id':road['id'],'part':road['part'],'surface_class':road['surface_class'],'name':road['name'],'highway':road['highway'],'platform_overlap_m2':float(areas.sum()),'core_overlap_m2':float(roadshape.intersection(core).area),'centerline_inside_core_m':float(roadline.intersection(core).length),'road_z_range_m':[float(heights.min()),float(heights.max())],'platform_surface_z_m':level})
    before_guard=local.copy();local[roadmask]=np.minimum(local[roadmask],localbase[roadmask])
    fixed=np.isfinite(new_limit)&(local>new_limit)
    if fixed.any():
        cut=np.where(fixed,local-new_limit,0)
        dist,nearest=distance_transform_edt(~fixed,return_indices=True)
        shoulder=np.clip(1-dist/3,0,1);shoulder=shoulder*shoulder*(3-2*shoulder)
        local-=np.where(inside,0,cut[tuple(nearest)]*shoulder).astype(np.float32)
        local=np.minimum(local,new_limit).astype(np.float32)
    assert np.all(local[roadmask]<=localbase[roadmask])
    out[np.ix_(ri,ci)]=local;protected[np.ix_(ri,ci)]|=roadmask
    free=inside&~roadmask
    assert np.max(np.abs(local[free]-(level-.08)))<2e-6
    delta=local-localbase
    record={'track_id':str(track['id']),'surface_z_m':level,'terrain_z_m':level-.08,'member_ids':[str(track['id'])]+[str(f['id']) for f in members],'footprint':mapping(footprint),'center_xy':[float(core.centroid.x),float(core.centroid.y)],'flat_margin_from_centerline_m':5,'feather_m':10,'source_valid_samples':int(valid.sum()),'surface_level_method':'median of official 0.5m DTM resampled at 1m inside the complete facility footprint; illustrative level platform, not surveyed finish floor','terrain_changed_cells':int((np.abs(delta)>.001).sum()),'terrain_max_cut_m':float(max(0,-delta.min())),'terrain_max_fill_m':float(max(0,delta.max())),'road_guard_cells_in_facility':int((roadmask&inside).sum()),'road_guard_cells_lowered_than_requested':int((local<before_guard-1e-6).sum()),'nearby_road_ids':sorted(set(nearby)),'road_overlaps':conflicts}
    facilities.append(record)
    print('SPORT_PLATFORM',json.dumps({k:v for k,v in record.items() if k not in ('footprint','nearby_road_ids')},ensure_ascii=False),flush=True)

assert np.all(out[protected]<=base[protected])
delta=out-base
report={'terrain_grid':'terrain_sports_leveled_1m.npz','base_grid':'terrain_roads_graded_1m.npz','path_adjustment':'sports_path_adjustment.npz' if adjustment is not None else None,'facilities':facilities,'summary':{'changed_cells':int((np.abs(delta)>.001).sum()),'max_cut_m':float(max(0,-delta.min())),'max_fill_m':float(max(0,delta.max())),'protected_road_cell_raise_m':float(max(0,delta[protected].max()))},'note':'Source survey data are unchanged. Touched road-cell corners retain the previous terrain as a ceiling; the locally relocated Philosophy Path additionally uses its new road-surface minus slab and clearance ceiling. Other roads are unchanged. The old overlap trench is restored as the level sports platform.'}
np.savez_compressed(ROOT/'terrain_sports_leveled_1m.npz',x=xs,y=ys,elevation=out)
(ROOT/'sports_platforms.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('SPORT_PLATFORMS_READY',json.dumps(report['summary']),flush=True)
