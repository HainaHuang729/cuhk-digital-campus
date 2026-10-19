"""Reference-based road heights, preserving v2 source-node topology and plan geometry."""
import io
import json
import sys
import zipfile
from collections import Counter,defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
CACHE=Path.home()/'.agent-reach/cuhk/high_detail_20260922'
sys.path.insert(0,str(Path.home()/'.agent-reach/cuhk/python'))
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix,diags,vstack
from scipy.sparse.linalg import cg,factorized

TILES=[r for r in json.loads((CACHE/'terrain_verified_manifest.json').read_text('utf-8')) if r['kind']=='dtm' and r.get('success',True)]
TILE_CACHE={}
MOTOR={'motorway','motorway_link','trunk','primary','secondary','secondary_link','tertiary','tertiary_link','residential','unclassified','service'}
STAIR_TYPES={8,12,13,16,20,21}


def survey_height(x,y):
    xx,yy=np.broadcast_arrays(np.asarray(x,dtype=float),np.asarray(y,dtype=float))
    shape=xx.shape;east=xx.ravel()+839400;north=yy.ravel()+831150
    out=np.full(east.shape,np.nan)
    for tile in TILES:
        e0,n0,e1,n1=tile['bbox_hk1980']
        indices=np.flatnonzero((east>=e0)&(east<e1)&(north>=n0)&(north<n1))
        if not len(indices):continue
        if tile['file'] not in TILE_CACHE:
            with zipfile.ZipFile(tile['file']) as archive:
                with Image.open(io.BytesIO(archive.read(tile['inner_file']))) as im:
                    arr=np.asarray(im,dtype=np.float32)
                    tags=dict(im.tag_v2)
                    assert tags[33550][0]==.5 and tags[33550][1]==.5
            TILE_CACHE[tile['file']]=arr
        arr=TILE_CACHE[tile['file']]
        u=np.clip((east[indices]-e0)/.5-.5,0,arr.shape[1]-1.000001)
        v=np.clip((n1-north[indices])/.5-.5,0,arr.shape[0]-1.000001)
        c,r=u.astype(int),v.astype(int);fx,fy=u-c,v-r
        corners=np.array([arr[r,c],arr[r,c+1],arr[r+1,c],arr[r+1,c+1]])
        values=corners[0]*(1-fx)*(1-fy)+corners[1]*fx*(1-fy)+corners[2]*(1-fx)*fy+corners[3]*fx*fy
        values[np.any(corners<=-9998,axis=0)]=np.nan
        out[indices]=values
    return out.reshape(shape)


def reference_segments():
    features=json.loads((CACHE/'roads/pedestrian_epsg2326.geojson').read_text('utf-8'))['features']
    starts=[];ends=[];indices=[]
    for fi,f in enumerate(features):
        tags=f['properties']
        if tags.get('Enabled')!=1 or tags.get('PositionCertainty')!=1:continue
        if tags.get('LevelSource') in (8,10):continue
        points=np.asarray(f['geometry']['coordinates'],dtype=float)
        points[:,:2]-=[839400,831150]
        for a,b in zip(points[:-1],points[1:]):
            count=max(1,int(np.ceil(np.linalg.norm(b[:2]-a[:2])/4)))
            for k in range(count):
                q=a+(b-a)*(k/count);r=a+(b-a)*((k+1)/count)
                if np.linalg.norm(q[:2]-r[:2])<.03:continue
                starts.append(q);ends.append(r);indices.append(fi)
    a=np.asarray(starts);b=np.asarray(ends)
    return features,a,b,np.asarray(indices),cKDTree((a[:,:2]+b[:,:2])/2)


def grade_metrics(profiles):
    groups=defaultdict(list);worst=[];reversals=Counter()
    for p in profiles:
        q=np.asarray(p['points']);ds=np.linalg.norm(np.diff(q[:,:2],axis=0),axis=1)
        slope=np.diff(q[:,2])/np.maximum(ds,.03)
        cls='stairs' if p['highway']=='steps' else 'vehicle' if p['highway'] in MOTOR else 'walkway'
        groups[cls].extend(abs(slope).tolist())
        sharp=(slope[:-1]*slope[1:]<0)&(np.minimum(abs(slope[:-1]),abs(slope[1:]))>.15)
        reversals[cls]+=int(sharp.sum())
        worst.append(dict(id=p['id'],part=p['part'],highway=p['highway'],surface_class=p['surface_class'],max_abs_grade=float(max(abs(slope),default=0))))
    return dict(by_type={k:dict(segment_count=len(v),median_abs_grade=float(np.median(v)),p95_abs_grade=float(np.percentile(v,95)),p99_abs_grade=float(np.percentile(v,99)),max_abs_grade=float(max(v)),sharp_adjacent_sign_reversals=reversals[k]) for k,v in groups.items()},worst_profiles=sorted(worst,key=lambda p:p['max_abs_grade'],reverse=True)[:30])


def main():
    network=json.loads((ROOT/'road_network_v2.json').read_text('utf-8'))
    profiles=network['profiles'];xyz=np.asarray(network['node_xyz']);count=len(xyz)
    dtm=survey_height(xyz[:,0],xyz[:,1]);valid_dtm=np.isfinite(dtm)
    before=grade_metrics(profiles)
    refs,ra,rb,ri,tree=reference_segments()
    refvec=rb[:,:2]-ra[:,:2];ref_len=np.linalg.norm(refvec,axis=1);refunit=refvec/ref_len[:,None]
    ft=np.array([f['properties']['FeatureType'] for f in refs]);loc=np.array([f['properties']['Location'] for f in refs]);weather=np.array([f['properties']['WeatherProof'] for f in refs])
    target_sum=np.zeros(count);weight_sum=np.zeros(count)
    anchor_values=defaultdict(list);match_records=[]
    curve_rows=[];curve_cols=[];curve_data=[];curve_weights=[];curve_limits=[]
    edge_limits={};edge_stairs={};edge_signs=defaultdict(set);row_index=0
    for pi,p in enumerate(profiles):
        ids=np.asarray(p['node_indices']);q=xyz[ids];xy=q[:,:2];n=len(q);kind=p['surface_class'];stairs=p['highway']=='steps';motor=p['highway'] in MOTOR
        base=np.where(valid_dtm[ids],dtm[ids],q[:,2]) if kind=='ground' else q[:,2].copy()
        base_weight=2.0 if kind=='ground' else .03 if kind in ('indoor','tunnel','below_ground') else .12
        target_sum[ids]+=base*base_weight;weight_sum[ids]+=base_weight
        v=np.diff(xy,axis=0);length=np.linalg.norm(v,axis=1);unit=v/np.maximum(length[:,None],.03)
        tangent=np.empty_like(xy);tangent[0]=unit[0];tangent[-1]=unit[-1]
        tangent[1:-1]=unit[:-1]+unit[1:];tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],.03)
        _,candidate=tree.query(xy,k=32)
        a=ra[candidate];b=rb[candidate];vv=refvec[candidate];tt=np.clip(np.sum((xy[:,None,:]-a[:,:,:2])*vv,axis=2)/np.maximum(ref_len[candidate]**2,.001),0,1)
        distance=np.linalg.norm(a[:,:,:2]+vv*tt[:,:,None]-xy[:,None,:],axis=2)
        alignment=abs(np.sum(refunit[candidate]*tangent[:,None,:],axis=2))
        rid=ri[candidate];types=ft[rid];locations=loc[rid]
        source_z=a[:,:,2]+tt*(b[:,:,2]-a[:,:,2])
        if stairs:
            permitted=np.isin(types,list(STAIR_TYPES)+[11])
            permitted&=locations!=2 if kind!='indoor' else locations==2
            max_distance=2.8
        elif kind=='tunnel':
            permitted=np.isin(types,[4,1])&(locations!=2)
            max_distance=2.3
        elif kind=='indoor':
            permitted=locations==2;max_distance=2.0
        elif kind=='below_ground':
            permitted=np.isin(types,[1,4,11,12])
            max_distance=2.0
        elif p['bridge'] not in ('no','') and not motor:
            # Explicit bridge segments are the strongest evidence; untyped footway is a fallback at mapped bridge approaches.
            permitted=np.isin(types,[2,1,11])&(locations!=2)
            max_distance=3.0
        elif motor and kind=='elevated':
            # An ordinary sidewalk below a vehicle flyover is not a deck-level control point.
            permitted=(types==2)&(locations==1)
            max_distance=min(6.,p['width']/2+1.5)
        elif motor:
            permitted=np.isin(types,[1,5,7,11,30,31,32,33])&(locations==1)&(weather[rid]==2)
            permitted&=abs(source_z-dtm[ids,None])<4.0
            max_distance=min(6.,p['width']/2+1.5)
        else:
            permitted=np.isin(types,[1,11,12,8,30,31,32,33])&(locations!=2)
            max_distance=2.4
        permitted&=(distance<=max_distance)&(alignment> (.55 if stairs else .75))
        score=distance+1.2*(1-alignment)
        if p['bridge'] not in ('no','') and not motor and not stairs:
            score+=np.where(types==2,0,1.7)
        # Distinct nearby vertical routes are not matched by Z proximity to a known-bad old profile.
        score[~permitted]=np.inf
        chosen=np.argmin(score,axis=1);rr=np.arange(n);best=score[rr,chosen]
        selected=np.isfinite(best)
        chosen_z=source_z[rr,chosen];chosen_rid=rid[rr,chosen];chosen_distance=distance[rr,chosen]
        ambiguous=np.any(permitted&(score<best[:,None]+.35)&(abs(source_z-chosen_z[:,None])>3),axis=1)
        selected&=~ambiguous
        if np.count_nonzero(selected)>=2:
            # A profile is matched only where source type, direction and horizontal proximity agree.
            for local in np.flatnonzero(selected):
                node=int(ids[local]);weight=8.0/(1+chosen_distance[local]**2)
                anchor_values[node].append((float(chosen_z[local]),weight,int(chosen_rid[local]),pi))
        else:
            selected[:]=False
        match_records.append(dict(id=p['id'],part=p['part'],surface_class=kind,highway=p['highway'],samples=n,
                                  reference_matched_samples=int(selected.sum()),ambiguous_vertical_samples=int(ambiguous.sum()),
                                  matched_fraction=float(selected.mean()),official_route_ids=sorted({int(refs[k]['properties']['PedestrianRouteID']) for k in chosen_rid[selected]}),
                                  median_horizontal_match_m=float(np.median(chosen_distance[selected])) if selected.any() else None))
        stair_sign=0
        if stairs:
            matched_at=np.flatnonzero(selected)
            if len(matched_at)>=2 and abs(chosen_z[matched_at[-1]]-chosen_z[matched_at[0]])>.6:
                stair_sign=int(np.sign(chosen_z[matched_at[-1]]-chosen_z[matched_at[0]]))
            elif abs(base[-1]-base[0])>1.:
                stair_sign=int(np.sign(base[-1]-base[0]))
        for k in range(n-1):
            edge=tuple(sorted((int(ids[k]),int(ids[k+1]))))
            limit=1.7 if stairs else .22 if motor else .45 if p['highway'] in ('path','track') else .35
            edge_limits[edge]=max(edge_limits.get(edge,0),limit)
            edge_stairs[edge]=edge_stairs.get(edge,False) or stairs
            if stairs and stair_sign:
                edge_signs[edge].add(stair_sign if ids[k]<ids[k+1] else -stair_sign)
        # Ordered per-route curvature preserves the source path through junctions instead of mixing unrelated branches.
        triplets=[(k-1,k,k+1,length[k-1],length[k]) for k in range(1,n-1)]
        if ids[0]==ids[-1] and n>3:
            triplets.append((n-2,0,1,length[-1],length[0]))
        for left_index,middle_index,right_index,left,right in triplets:
            if min(left,right)<.03:continue
            curve_rows.extend([row_index]*3);curve_cols.extend([int(ids[left_index]),int(ids[middle_index]),int(ids[right_index])]);curve_data.extend([1/left,-1/left-1/right,1/right])
            curve_weights.append((3 if stairs else 45 if motor else 18)*(left+right)/2)
            curve_limits.append(.9 if stairs else (.045 if motor else .085)*(left+right)/2)
            row_index+=1
    anchor_conflicts=[]
    for node,values in anchor_values.items():
        vals=np.asarray([v[0] for v in values]);ww=np.asarray([v[1] for v in values])
        order=np.argsort(vals);chosen=order[np.searchsorted(np.cumsum(ww[order]),ww.sum()/2)]
        good=abs(vals-vals[chosen])<=2.0
        if not good.all():anchor_conflicts.append(dict(node_index=node,xyz=xyz[node].tolist(),reference_z=vals.tolist(),accepted_z=float(vals[chosen])))
        weight=min(20.,ww[good].sum())
        target_sum[node]+=float(np.average(vals[good],weights=ww[good]))*weight;weight_sum[node]+=weight
    target=target_sum/np.maximum(weight_sum,1e-12)
    curvature=coo_matrix((curve_data,(curve_rows,curve_cols)),shape=(row_index,count)).tocsr()
    base_matrix=diags(weight_sum)+curvature.T@diags(curve_weights)@curvature
    rhs=target_sum.copy();z,info=cg(base_matrix,rhs,x0=target,rtol=1e-8,maxiter=3500)
    assert info==0,info
    edges=np.asarray(list(edge_limits));elen=np.linalg.norm(xyz[edges[:,1],:2]-xyz[edges[:,0],:2],axis=1)
    limits=np.asarray(list(edge_limits.values()));elen=np.maximum(elen,.03)
    diff=coo_matrix((np.r_[-1/elen,1/elen],(np.r_[np.arange(len(edges)),np.arange(len(edges))],np.r_[edges[:,0],edges[:,1]])),shape=(len(edges),count)).tocsr()
    lower,upper=-limits.copy(),limits.copy()
    for k,edge in enumerate(map(tuple,edges)):
        signs=edge_signs[edge]
        if signs=={1}:lower[k]=0.
        elif signs=={-1}:upper[k]=0.
    constraint=vstack((diff,curvature),format='csr')
    lower=np.r_[lower,-np.asarray(curve_limits)];upper=np.r_[upper,np.asarray(curve_limits)]
    # ADMM enforces bounded longitudinal grades without breaking common OSM nodes.
    # Actual stairs have their separate allowance and a monotonic flight where reference endpoints establish direction.
    rho=500.
    solve=factorized((base_matrix+rho*(constraint.T@constraint)).tocsc())
    slope=constraint@z;bounded=np.clip(slope,lower,upper);dual=np.zeros(len(lower))
    for iteration in range(500):
        z=solve(rhs+rho*(constraint.T@(bounded-dual)))
        slope=constraint@z;bounded=np.clip(slope+dual,lower,upper);dual+=slope-bounded
        violation=float(np.max(np.maximum(lower-slope,slope-upper)))
        if violation<.0005 and iteration>25:break
    assert np.isfinite(z).all()
    network['node_xyz']=np.column_stack((xyz[:,:2],z)).tolist()
    for p,m in zip(profiles,match_records):
        ids=np.asarray(p['node_indices']);p['points']=np.column_stack((xyz[ids,:2],z[ids])).tolist()
        p['reference_match']=m
        p['height_source']='CEDD 2020 0.5m DTM and semantically matched official 3D pedestrian XYZ; smooth shared-node fit'
        p['cross_section_note']='Use one scalar profile height per station for both edges; do not independently nearest-project road edges to adjacent segments.'
    for junction in network['junctions']:
        idx=junction['node_index'];junction['xyz']=network['node_xyz'][idx];junction['point']=network['node_xyz'][idx]
    after=grade_metrics(profiles)
    gaps=[]
    for j in network['junctions']:
        values=[]
        for pi in j['profile_indices']:
            p=profiles[pi];at=p['node_indices'].index(j['node_index']);values.append(p['points'][at][2])
        gaps.append(max(values)-min(values))
    assert max(gaps)==0.
    anchor_errors=[abs(z[n]-np.median([v[0] for v in vv])) for n,vv in anchor_values.items()]
    worst_before=json.loads((ROOT/'road_surface_after.json').read_text('utf-8'))['all']
    residual_ids={int(p['id']) for p in worst_before if p['buried_probes']>0}
    residuals=[]
    for pi,p in enumerate(profiles):
        if p['id'] not in residual_ids:continue
        old=np.asarray(json.loads((ROOT/'road_network_v2.json').read_text('utf-8'))['profiles'][pi]['points'])[:,2]
        new=np.asarray(p['points'])[:,2]
        residuals.append(dict(id=p['id'],highway=p['highway'],surface_class=p['surface_class'],reference_match=p['reference_match'],median_height_change_m=float(np.median(new-old)),max_abs_height_change_m=float(np.max(abs(new-old)))))
    stats=dict(version=3,profile_count=len(profiles),node_count=count,actual_max_shared_node_gap_m=max(gaps),
               plan_geometry_changed=False,original_osm_topology_preserved=True,source_dtm_spacing_m=.5,dtm_tiles_used=len(TILE_CACHE),
               nodes_with_valid_dtm=int(valid_dtm.sum()),official_xyz_anchor_nodes=len(anchor_values),
               profiles_with_official_xyz_matches=sum(r['reference_matched_samples']>0 for r in match_records),
               reference_anchor_error_median_m=float(np.median(anchor_errors)),reference_anchor_error_p95_m=float(np.percentile(anchor_errors,95)),
               ambiguous_shared_node_reference_conflicts=len(anchor_conflicts),
               bounded_fit_iterations=iteration+1,maximum_grade_or_curvature_constraint_violation=violation,
               median_abs_height_change_m=float(np.median(abs(z-xyz[:,2]))),p95_abs_height_change_m=float(np.percentile(abs(z-xyz[:,2]),95)),
               max_abs_height_change_m=float(np.max(abs(z-xyz[:,2]))),
               before_grades=before['by_type'],after_grades=after['by_type'],
               uniform_surface_offset_m=.15,
               limitation='Official pedestrian source XY accuracy 1m/Z accuracy 2m and approximate cross-source vertical agreement; sampling is not a surveyed road design. Unmatched bridge/tunnel levels retain a weak prior and should be checked against local terrain/structure. No layer number is converted into an elevation.')
    network['stats']=stats
    network['surface_height_note']='Road top = profile reference z + 0.15m. Both edges at each station share the same height; create a common junction patch only for existing shared source nodes.'
    network['terrain_note']='Reference-based profile fit permits local cut/fill around genuinely visible road surfaces; do not join unrelated layered crossings. Keep underground and indoor routes hidden as references.'
    report=dict(stats=stats,profile_reference_matches=match_records,reference_conflicts=anchor_conflicts,
                previous_residual_33_profiles=residuals,largest_remaining_profile_grades=after['worst_profiles'],source_tiles=list(TILE_CACHE))
    (ROOT/'road_network_v3.json').write_text(json.dumps(network,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'road_network_v3_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
