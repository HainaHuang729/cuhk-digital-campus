"""Restore cached OSM node topology, preserving grade-separated crossings and mapped XY."""
import json
from collections import Counter,defaultdict

import numpy as np

from diagnose_road_network import ROOT,coordinate_key,load_roads,diagnose,profile_height,semantics
from scipy.sparse import coo_matrix,diags,eye
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import cg
from shapely.geometry import Point


def main():
    roads,old_stats=load_roads()
    audit=diagnose(roads,old_stats)
    grid=np.load(ROOT/'terrain_refined_display.npz')
    xs,ys,z=grid['x'],grid['y'],grid['elevation']

    def terrain_height(x,y):
        u=np.clip((np.asarray(x)-xs[0])/5,0,len(xs)-1.00001)
        v=np.clip((ys[0]-np.asarray(y))/5,0,len(ys)-1.00001)
        a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
        return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)

    # Every exact original OSM node identity is retained, including the endpoints of ramps, steps and bridge approaches.
    # No geometric proximity key joins distinct nodes; no inferred connection is made at grade-separated intersections.
    xy=[];lookup={};source_ids=[];targets=[];samples=[];road_nodes=[];edges=set();members=defaultdict(set)
    inferred=defaultdict(list)
    for event in audit['intersection_events']:
        if event['connect'] and event['source_node'] is None:
            for index in (event['a'],event['b']):
                inferred[index].append(event['xy'])
    for index,road in enumerate(roads):
        raw=road['xy'];line=road['line']
        station=np.concatenate(([0],np.cumsum(np.linalg.norm(np.diff(raw,axis=0),axis=1))))
        distances=list(station)
        for start,end in zip(station[:-1],station[1:]):
            distances.extend(np.linspace(start,end,max(2,int(np.ceil((end-start)/2))+1))[1:-1])
        distances.extend(line.project(Point(p)) for p in inferred[index])
        distances=np.unique(np.round(distances,9))
        points=np.column_stack((np.interp(distances,station,raw[:,0]),np.interp(distances,station,raw[:,1])))
        # Keep original vertex coordinates bit-for-bit rather than introducing station-rounding drift at source nodes.
        for at,p in zip(station,raw):
            points[int(np.argmin(abs(distances-at)))]=p
        old=road['old']
        if old is not None:
            # Ordered arc length is essential: a closed line projects its final point back to zero.
            # Nearest-point projection also loses ordering on retraced or self-intersecting geometry.
            old_lengths=np.linalg.norm(np.diff(old[:,:2],axis=0),axis=1)
            old_station=np.r_[0.,np.cumsum(old_lengths)]
            assert old_station[-1]>0 and np.all(np.diff(old_station)>=0),road['id']
            old_station*=station[-1]/old_station[-1]
            assert abs(old_station[-1]-station[-1])<1e-7,road['id']
            if np.linalg.norm(raw[0]-raw[-1])<1e-7:
                assert old_station[-1]>0 and abs(old_station[-1]-line.length)<1e-6,road['id']
            baseline=np.interp(distances,old_station,old[:,2])
            assert abs(float(np.interp(station[-1],old_station,old[:,2]))-float(old[-1,2]))<1e-7,road['id']
        else:
            # Missing indoor/tunnel profiles are restored as topology, but their display heights remain unmeasured.
            baseline=terrain_height(points[:,0],points[:,1])
        ids=[]
        for local,(p,target) in enumerate(zip(points,baseline)):
            keyxy=coordinate_key(p);node=road['source_nodes'].get(keyxy)
            key=('osm_node',node) if node is not None else ('road_sample',index,local)
            if keyxy in {coordinate_key(q) for q in inferred[index]}:
                key=('inferred_junction',semantics(road),keyxy)
            if key not in lookup:
                lookup[key]=len(xy);xy.append(p.tolist());targets.append(0.);samples.append(0);source_ids.append(node)
            idx=lookup[key]
            targets[idx]+=float(target);samples[idx]+=1;members[idx].add(index)
            if not ids or idx!=ids[-1]:ids.append(idx)
        road_nodes.append(ids)
        edges.update(tuple(sorted((a,b))) for a,b in zip(ids[:-1],ids[1:]) if a!=b)
    xy=np.asarray(xy);uv=np.asarray(sorted(edges));target=np.asarray(targets)/np.asarray(samples)
    lengths=np.linalg.norm(xy[uv[:,1]]-xy[uv[:,0]],axis=1)
    weights=1/np.maximum(lengths,.5)
    adjacency=coo_matrix((np.r_[weights,weights],(np.r_[uv[:,0],uv[:,1]],np.r_[uv[:,1],uv[:,0]])),shape=(len(xy),len(xy))).tocsr()
    degree=np.asarray(adjacency.sum(axis=1)).ravel()
    laplacian=eye(len(xy))-diags(1/np.maximum(degree,.001))@adjacency
    # ponytail: illustrative graph smoothing only. Surveyed road levels and engineered gradients are outside this reconstruction.
    matrix=eye(len(xy))+450*(laplacian.T@laplacian)
    smooth,info=cg(matrix,target,x0=target,rtol=1e-8,maxiter=3500)
    assert info==0,info
    assert np.isfinite(smooth).all()
    profiles=[]
    for index,(road,ids) in enumerate(zip(roads,road_nodes)):
        tags=road['tags'];layer=road['layer']
        if road['highway']=='trailhead':surface_class='non_road_area_tagged_as_highway'
        elif road['tunnel'] not in ('no',''):surface_class='tunnel'
        elif tags.get('indoor')=='yes' or road['highway']=='corridor':surface_class='indoor'
        elif road['bridge'] not in ('no','') or float(layer)>0:surface_class='elevated'
        elif float(layer)<0:surface_class='below_ground'
        else:surface_class='ground'
        profiles.append(dict(id=road['id'],part=road['part'],tags=tags,highway=road['highway'],width=road['width'],layer=layer,
                             bridge=road['bridge'],tunnel=road['tunnel'],campus=road['campus'],surface_class=surface_class,
                             points=np.column_stack((xy[ids],smooth[ids])).tolist(),node_indices=ids,
                             junction_nodes=[dict(point_index=k,node_index=n,osm_node_id=source_ids[n]) for k,n in enumerate(ids) if len(members[n])>1],
                             height_source='topology-corrected prior illustrative profile' if road['old'] is not None else 'source display terrain; tunnel/indoor absolute elevations unmeasured'))
    junctions=[]
    graph_degree=np.bincount(uv.ravel(),minlength=len(xy))
    for idx,indices in members.items():
        if len(indices)>1:
            layers=sorted({roads[r]['layer'] for r in indices})
            junctions.append(dict(node_index=idx,osm_node_id=source_ids[idx],point=[*xy[idx].tolist(),float(smooth[idx])],
                                  xyz=[*xy[idx].tolist(),float(smooth[idx])],degree=int(graph_degree[idx]),
                                  profile_indices=sorted(indices),osm_way_ids=sorted({roads[r]['id'] for r in indices}),layers=layers,
                                  incident_roads=[dict(profile_index=r,id=roads[r]['id'],part=roads[r]['part'],width=roads[r]['width'],highway=roads[r]['highway'],layer=roads[r]['layer'],surface_class=profiles[r]['surface_class']) for r in sorted(indices)],
                                  connection_evidence='shared original OSM node ID' if source_ids[idx] is not None else 'explicit same-level inferred intersection',
                                  cross_layer_source_transition=len(layers)>1))
    # Check actual exported profiles at every diagnosed source junction and every separated crossing.
    revised=[]
    for road,profile in zip(roads,profiles):
        revised.append(dict(road,old=np.asarray(profile['points'])))
    connected_gaps=[];separated=[]
    for event in audit['intersection_events']:
        a,b=event['a'],event['b'];pt=event['xy']
        gap=abs(profile_height(revised[a],pt)-profile_height(revised[b],pt))
        event['new_centerline_gap_m']=gap
        event['new_rendered_surface_gap_m']=gap  # All road tops use exactly the same +0.15 m display offset.
        if event['connect']:connected_gaps.append(gap)
        else:
            separated.append(dict(ids=event['ids'],xy=pt,layers=event['layers'],bridges=event['bridges'],tunnels=event['tunnels'],height_difference_m=gap))
    components,_=connected_components(adjacency,directed=False)
    largest=max(connected_gaps,default=0.)
    assert largest<1e-5,largest
    source_xy_displacement=0.
    maximum_segment_length=0.
    for road,profile in zip(roads,profiles):
        points=np.asarray(profile['points'])[:,:2]
        for pt in road['xy']:
            source_xy_displacement=max(source_xy_displacement,float(np.min(np.linalg.norm(points-pt,axis=1))))
        maximum_segment_length=max(maximum_segment_length,float(np.max(np.linalg.norm(np.diff(points,axis=0),axis=1))))
    assert source_xy_displacement<1e-7,source_xy_displacement
    assert maximum_segment_length<2.000001,maximum_segment_length
    adjustment=smooth-target
    after=dict(road_profiles=len(profiles),shared_profile_nodes=len(xy),network_edges=len(uv),source_junction_nodes=len(junctions),
               actual_cross_layer_source_junction_nodes=sum(j['cross_layer_source_transition'] for j in junctions),
               measured_connected_junction_pairs=len(connected_gaps),max_shared_junction_gap_m=largest,
               max_shared_rendered_surface_gap_m=largest,connected_junction_gaps_above_0_05m=sum(g>.05 for g in connected_gaps),
               repaired_source_layer_transition_pairs=audit['before']['classification_counts'].get('source_shared_node_layer_transition',0),
               inferred_junction_pairs=audit['before']['classification_counts'].get('same_level_geometric_intersection_without_shared_source_node',0),
               snapped_endpoint_count=0,added_unmapped_road_length_m=0.,retained_uncertain_near_endpoint_pairs=len(audit['near_endpoint_candidates']),
               separated_crossing_pairs_preserved=len(separated),graph_components=int(components),
               rms_additional_height_adjustment_m=float(np.sqrt(np.mean(adjustment**2))),max_additional_height_adjustment_m=float(np.max(abs(adjustment))),
               surface_class_counts=dict(Counter(p['surface_class'] for p in profiles)),uniform_surface_offset_m=.15,
               maximum_source_xy_displacement_m=source_xy_displacement,maximum_plan_segment_length_m=maximum_segment_length,
               limitation='DTM and schematic profiles do not establish engineered bridge clearance, indoor floor levels or tunnel depth. Layer-separated profiles remain topologically independent.')
    audit['after']=after
    audit['separated_crossing_clearance_samples']=sorted(separated,key=lambda e:e['height_difference_m'])
    audit['source_xy_preservation']='All original source vertices are inserted without snapping; only interpolated points densify existing segments.'
    audit['repair_policy']='Connect original shared OSM node IDs including layer-changing approaches; do not snap distinct nearby nodes, close crop-boundary gaps, or connect grade-separated / access-restricted geometric crossings.'
    output=dict(profiles=profiles,junctions=junctions,node_xyz=np.column_stack((xy,smooth)).tolist(),osm_node_ids=source_ids,stats=after,
                surface_height_note='points contain centerline reference height. Render all profile road tops at z + 0.15 m; do not reintroduce per-OSM-ID offsets.',
                terrain_note='Do not use elevated, below-ground, tunnel, indoor, or non-road profiles to flatten the surface terrain.')
    (ROOT/'road_network_v2.json').write_text(json.dumps(output,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    (ROOT/'road_network_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(after,ensure_ascii=True),flush=True)


if __name__=='__main__':
    main()
