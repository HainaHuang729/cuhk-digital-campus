"""Remove road-shoulder fill from the verified hostel ground-floor frontage."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
from shapely.geometry import shape
from shapely import points,distance
grid=np.load(ROOT/'terrain_roads_graded_1m.npz');xs,ys,z=grid['x'],grid['y'],grid['elevation'].copy()
alignment={a['osm_id']:a for a in json.loads((ROOT/'building_terrain_alignment.json').read_text('utf-8'))}
features=json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'];changes=[]
for f in features:
    if f['kind']!='building' or str(f['id'])!='135193165':continue
    g=shape(f['geometry']);x0,y0,x1,y1=g.bounds
    ix=np.flatnonzero((xs>=x0-10)&(xs<=x1+10));iy=np.flatnonzero((ys>=y0-10)&(ys<=y1+10));xx,yy=np.meshgrid(xs[ix],ys[iy]);dd=distance(points(xx,yy),g)
    floor=alignment[str(f['id'])]['new_base_m']-.3;old=z[np.ix_(iy,ix)].copy();gap=old-floor
    # The independently checked low frontage is about105m, whereas upper
    # connections are separate. Clear modest fill at that frontage, leaving
    # terrain >10m above its floor as the distinct upper-level landscape.
    # Ray-picked remaining mound lies about3-5m beyond the source footprint.
    # Clear the frontage to5m and feather back to the hill over the next5m.
    w=np.clip((10-dd)/5,0,1);w=w*w*(3-2*w);w*=np.clip((10-gap)/2,0,1)
    cut=np.maximum(gap,0)*w;z[np.ix_(iy,ix)]=old-cut
    changes.append({'osm_id':str(f['id']),'floor_clearance_level_m':floor,'changed_samples':int(np.sum(cut>.01)),'max_lowering_m':float(cut.max()),'basis':'Verified Residence Road ground paths104-108m and CEDD DTM; remove local shoulder mound from lower facade, preserve upper passages.'})
assert np.all(z<=grid['elevation']+1e-5),'This pass must never raise terrain into a road'
for x,y in [(-256,240),(-257,241),(-260,239)]:
    r=int(round(ys[0]-y));c=int(round(x-xs[0]))
    assert z[r,c]<106.0,('Verified frontage mound remains',x,y,float(z[r,c]))
np.savez_compressed(ROOT/'terrain_roads_graded_1m.npz',x=xs,y=ys,elevation=z)
(ROOT/'foundation_clearance_report.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(changes,ensure_ascii=False))
