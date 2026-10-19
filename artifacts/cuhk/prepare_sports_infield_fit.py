"""Fit each complete infield layout inside the running-track inner edge."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import shapely
from shapely.geometry import shape,Polygon,mapping
from shapely.affinity import scale
features={str(f['id']):f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']}
facilities=json.loads((ROOT/'sports_platforms.json').read_text('utf-8'))['facilities']
records=[]
for facility in facilities:
    track_id=facility['track_id'];member_ids=[i for i in facility['member_ids'] if i!=track_id]
    outline=Polygon(features[track_id]['geometry']['coordinates'])
    envelope=shapely.union_all([shape(features[i]['geometry']) for i in member_ids])
    # 4m half track width plus 0.3m covers the markings/goal-footprint allowance.
    allowable=outline.buffer(-4.3)
    center=facility['center_xy']
    def fit(s):return scale(envelope,xfact=s,yfact=s,origin=tuple(center))
    if allowable.covers(envelope):factor=1.
    else:
        lo,hi=0.,1.
        for _ in range(50):
            mid=(lo+hi)/2
            if allowable.covers(fit(mid)):lo=mid
            else:hi=mid
        factor=lo-1e-5
    fitted=fit(factor)
    assert allowable.covers(fitted)
    records.append({'track_id':track_id,'center_xy':center,'scale':factor,'member_ids':member_ids,'track_half_width_m':4.0,'additional_infield_allowance_m':.3,'initial_outside_allowable_area_m2':envelope.difference(allowable).area,'fitted_outside_allowable_area_m2':fitted.difference(allowable).area,'fitted_clearance_to_track_centerline_m':outline.boundary.distance(fitted),'original_layout_bounds':list(envelope.bounds),'fitted_layout_bounds':list(fitted.bounds),'allowable_footprint':mapping(allowable),'note':'Uniform XY scaling about facility center for all member surfaces, markings and goal/net layouts; retain each facility Z unchanged.'})
(ROOT/'sports_infield_fit.json').write_text(json.dumps({'facilities':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{k:v for k,v in r.items() if k!='allowable_footprint'} for r in records],ensure_ascii=False,indent=2),flush=True)
