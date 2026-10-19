"""Measure source topology and actual profile junction gaps without changing scene files."""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
CACHE = Path.home()/'.agent-reach/cuhk'
sys.path.insert(0,str(CACHE/'python'))
from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

WIDTHS={'motorway':10,'motorway_link':6,'trunk':9,'primary':9,'secondary':8,'secondary_link':6,'tertiary':7,'tertiary_link':5,'residential':5,'service':4,'unclassified':5,'footway':1.8,'path':1.4,'steps':2,'pedestrian':3,'cycleway':2.5,'track':3}


def coordinate_key(xy):
    return tuple(round(float(v),6) for v in xy[:2])


def load_roads():
    data=json.loads((ROOT/'geodata.json').read_text('utf-8'))
    old=json.loads((ROOT/'smooth_road_profiles.json').read_text('utf-8'))
    source=json.loads((CACHE/'osm_full.json').read_text('utf-8'))
    origin=np.asarray(data['origin_hk1980'])
    transform=Transformer.from_crs(4326,2326,always_xy=True)
    ways={e['id']:e for e in source['elements'] if e['type']=='way'}
    old_by_id=defaultdict(list)
    for profile in old['profiles']:
        old_by_id[profile['id']].append(np.asarray(profile['points']))
    roads=[]
    for f in data['features']:
        if f['kind']!='road' or f['tags'].get('highway') in ('construction','proposed'):
            continue
        tags=f['tags'];geo=f['geometry']
        lines=[geo['coordinates']] if geo['type']=='LineString' else geo['coordinates'] if geo['type']=='MultiLineString' else []
        source_xy={}
        e=ways.get(f['id'],{})
        for node,g in zip(e.get('nodes',[]),e.get('geometry',[])):
            if 'lon' in g:
                xy=np.asarray(transform.transform(g['lon'],g['lat']))-origin
                source_xy[coordinate_key(xy)]=node
        for part,coords in enumerate(lines):
            xy=np.asarray(coords,dtype=float)
            if len(xy)<2:
                continue
            line=LineString(xy)
            if line.length<1e-5:
                continue
            width=WIDTHS.get(tags['highway'],3)
            try:width=float(tags.get('width',width))
            except (ValueError,TypeError):pass
            layer=str(tags.get('layer','0'))
            bridge=tags.get('bridge','no')
            tunnel=tags.get('tunnel','no')
            candidates=old_by_id.get(f['id'],[])
            previous=min(candidates,key=lambda p:LineString(p[:,:2]).hausdorff_distance(line)) if candidates else None
            source_nodes={k:n for k,n in source_xy.items() if Point(k).distance(line)<2e-5}
            roads.append(dict(id=f['id'],part=part,tags=tags,highway=tags['highway'],width=width,layer=layer,bridge=bridge,tunnel=tunnel,
                              campus=f['campus'],xy=xy,line=line,source_nodes=source_nodes,old=previous))
    return roads,old['stats']


def profile_height(road,xy):
    p=road['old']
    if p is None:
        return None
    a=p[:-1];b=p[1:];v=b[:,:2]-a[:,:2]
    t=np.clip(np.sum((np.asarray(xy)-a[:,:2])*v,axis=1)/np.maximum(np.sum(v*v,axis=1),1e-14),0,1)
    d=np.sum((a[:,:2]+v*t[:,None]-xy)**2,axis=1)
    i=int(np.argmin(d))
    return float(a[i,2]+t[i]*(b[i,2]-a[i,2]))


def endpoint(road,xy,tolerance=1e-5):
    return bool(min(np.linalg.norm(road['xy'][0]-xy),np.linalg.norm(road['xy'][-1]-xy))<=tolerance)


def semantics(road):
    t=road['tags']
    return (road['layer'],t.get('level',''),road['bridge'] not in ('no',''),road['tunnel'] not in ('no',''),t.get('indoor')=='yes')


def safe_inferred(a,b,xy):
    if semantics(a)!=semantics(b):return False
    if a['bridge'] not in ('no','') or a['tunnel'] not in ('no','') or a['layer']!='0':return False
    if a['tags'].get('indoor')=='yes' or b['tags'].get('indoor')=='yes':return False
    if any(r['highway'] in ('motorway','motorway_link','corridor','trailhead') for r in (a,b)):return False
    if any(r['tags'].get('access') in ('no','private') for r in (a,b)):return False
    if any(r['tags'].get('noexit')=='yes' for r in (a,b)):return False
    if any(r['highway']=='steps' for r in (a,b)) and not (endpoint(a,xy) or endpoint(b,xy)):return False
    return True


def intersection_points(geom):
    if geom.is_empty:return []
    if geom.geom_type=='Point':return [geom]
    if geom.geom_type in ('MultiPoint','GeometryCollection'):
        return [p for g in geom.geoms for p in intersection_points(g)]
    if geom.geom_type=='LineString':
        return [Point(geom.coords[0]),Point(geom.coords[-1])]
    if geom.geom_type=='MultiLineString':
        return [p for g in geom.geoms for p in intersection_points(g)]
    return []


def diagnose(roads,old_stats):
    lines=[r['line'] for r in roads];tree=STRtree(lines)
    events=[];counts=Counter()
    for i,a in enumerate(roads):
        for j in tree.query(a['line'],predicate='intersects'):
            j=int(j)
            if j<=i:continue
            b=roads[j]
            for point in intersection_points(a['line'].intersection(b['line'])):
                xy=np.asarray(point.coords[0]);key=coordinate_key(xy)
                na=a['source_nodes'].get(key);nb=b['source_nodes'].get(key)
                source_shared=na is not None and na==nb
                same_layer=a['layer']==b['layer']
                if source_shared:
                    reason='source_shared_node' if same_layer else 'source_shared_node_layer_transition'
                    connect=True
                elif safe_inferred(a,b,xy):
                    reason='same_level_geometric_intersection_without_shared_source_node'
                    connect=True
                else:
                    reason='separate_layers_or_semantically_ambiguous_crossing'
                    connect=False
                ha,hb=profile_height(a,xy),profile_height(b,xy)
                gap=abs(ha-hb) if ha is not None and hb is not None else None
                event=dict(a=i,b=j,ids=[a['id'],b['id']],xy=xy.tolist(),layers=[a['layer'],b['layer']],
                           bridges=[a['bridge'],b['bridge']],tunnels=[a['tunnel'],b['tunnel']],
                           source_node=na if source_shared else None,reason=reason,connect=connect,
                           old_centerline_gap_m=gap,old_rendered_surface_gap_m=abs((ha+.002*(a['id']%101))-(hb+.002*(b['id']%101))) if gap is not None else None,
                           at_endpoints=[endpoint(a,xy),endpoint(b,xy)])
                events.append(event);counts[reason]+=1
    # Measured endpoint-to-line near misses. Only exact source topology is compulsory; nearby distinct OSM nodes can be intentional.
    near=[];seen=set()
    for i,a in enumerate(roads):
        for end_index,xy in [(0,a['xy'][0]),(-1,a['xy'][-1])]:
            point=Point(xy)
            for j in tree.query(point.buffer(.800001)):
                j=int(j)
                if i==j:continue
                b=roads[j];d=point.distance(b['line'])
                if d<1e-5 or d>.8:continue
                projected=b['line'].interpolate(b['line'].project(point))
                target=np.asarray(projected.coords[0])
                key=(i,end_index,j,coordinate_key(target))
                if key in seen:continue
                seen.add(key)
                outward=xy-a['xy'][1 if end_index==0 else -2]
                toward=target-xy
                cosine=float(np.dot(outward,toward)/(max(np.linalg.norm(outward),1e-9)*d))
                source_a=a['source_nodes'].get(coordinate_key(xy))
                source_b=b['source_nodes'].get(coordinate_key(target))
                near.append(dict(a=i,b=j,ids=[a['id'],b['id']],endpoint=end_index,xy=xy.tolist(),target_xy=target.tolist(),distance_m=d,
                                 tangent_alignment_cosine=cosine,semantics_compatible=safe_inferred(a,b,xy),
                                 source_nodes=[source_a,source_b],action='retain_distinct_source_nodes_pending_specific_connection_evidence'))
    connected=[e for e in events if e['connect'] and e['old_centerline_gap_m'] is not None]
    examples=sorted(connected,key=lambda e:e['old_centerline_gap_m'],reverse=True)
    summary=dict(source_road_parts=len(roads),old_profile_count=old_stats['road_profiles'],classification_counts=dict(counts),
                 same_layer_intersections_without_shared_source_node=sum(e['source_node'] is None and e['layers'][0]==e['layers'][1] for e in events),
                 measured_connected_junction_pairs=len(connected),measured_max_connected_centerline_gap_m=max((e['old_centerline_gap_m'] for e in connected),default=0),
                 measured_max_connected_rendered_surface_gap_m=max((e['old_rendered_surface_gap_m'] for e in connected),default=0),
                 measured_connected_centerline_gaps_above_0_05m=sum(e['old_centerline_gap_m']>.05 for e in connected),
                 endpoints_within_0_8m_of_other_line=len(near),
                 missing_old_profiles=[dict(id=r['id'],part=r['part'],highway=r['highway'],layer=r['layer'],tunnel=r['tunnel']) for r in roads if r['old'] is None],
                 old_reported_max_shared_junction_gap_m=old_stats.get('max_shared_junction_gap_m'),
                 old_reported_gap_is_literal_not_network_measurement=True,
                 previous_render_per_road_offset_formula='.15 + .002 * (osm_id % 101) metres above profile',
                 topology_source='Cached original OSM way node IDs in osm_full.json; inferred crossings are separately identified')
    return dict(before=summary,largest_old_connected_gaps=examples[:30],intersection_events=events,near_endpoint_candidates=near)


if __name__=='__main__':
    roads,stats=load_roads();audit=diagnose(roads,stats)
    (ROOT/'road_network_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit['before'],ensure_ascii=True))
    print('LARGEST_OLD_GAPS',json.dumps(audit['largest_old_connected_gaps'][:6],ensure_ascii=True))
