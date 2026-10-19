"""Place illustrative trees within mapped woodland, with clearance from mapped facilities."""
import json,sys,random,math
from pathlib import Path
root=Path(__file__).resolve().parent; cache=Path.home()/'.agent-reach/cuhk'
sys.path.insert(0,str(cache/'python'))
from pyproj import Transformer
from shapely.geometry import shape,Polygon,Point,LineString,box
from shapely.ops import unary_union
from shapely import contains_xy
from shapely.affinity import translate
import numpy as np
tr=Transformer.from_crs(4326,2326,always_xy=True)
def xy(lon,lat):
    x,y=tr.transform(lon,lat);return x-839400,y-831150
source=json.loads((cache/'vegetation.json').read_text('utf-8'))
features=json.loads((root/'geodata.json').read_text('utf-8'))['features']
exclusions=[]
for f in features:
    g=shape(f['geometry']); kind=f['kind']; t=f['tags']
    if kind=='building': g=g.buffer(5)
    elif kind=='road':
        if t.get('tunnel')=='yes': continue
        hw=t['highway']; g=g.buffer(4.5 if hw in ('path','footway','steps') else 7)
    elif kind in ('sport','water'):g=g.buffer(4)
    else:continue
    exclusions.append(g)
exclusion=unary_union(exclusions)
wood=[]; actual=[]; rows=[]
for e in source['elements']:
    tags=e['tags']
    if e['type']=='node':actual.append((*xy(e['lon'],e['lat']),e['id']));continue
    p=[xy(g['lon'],g['lat']) for g in e.get('geometry',[]) if 'lon' in g]
    if len(p)<2:continue
    if tags.get('natural')=='tree_row':rows.append((LineString(p),e['id']))
    elif (tags.get('natural')=='wood' or tags.get('landuse')=='forest') and p[0]==p[-1]:wood.append(Polygon(p).buffer(0))
forest=unary_union(wood).intersection(box(-1185,-1185,1185,1185)).difference(exclusion)
rng=random.Random(2849)
x,y=np.meshgrid(np.arange(-1180,1180,18),np.arange(-1180,1180,18)); x=x.ravel(); y=y.ravel()
x=x+np.array([rng.uniform(-6,6) for _ in x]); y=y+np.array([rng.uniform(-6,6) for _ in y])
mask=contains_xy(forest,x,y)
points=[{'x':float(a),'y':float(b),'h':rng.uniform(7,12),'r':rng.uniform(3.3,5.6),'source':'woodland_area_scatter'} for a,b in zip(x[mask],y[mask])]
for line,oid in rows:
    for d in np.arange(0,line.length,9):
        p=line.interpolate(d)
        if box(-1185,-1185,1185,1185).contains(p) and not exclusion.contains(p):
            points.append({'x':p.x,'y':p.y,'h':rng.uniform(6.5,9.5),'r':rng.uniform(2.8,4),'source':f'mapped_tree_row_{oid}'})
for x,y,oid in actual:
    if not (-1185<x<1185 and -1185<y<1185):continue
    # Individual point locations are retained unless they fall inside buildings or sports facilities.
    if any(shape(f['geometry']).contains(Point(x,y)) for f in features if f['kind'] in ('building','sport')): continue
    points.append({'x':x,'y':y,'h':rng.uniform(7,11),'r':rng.uniform(3.5,5),'source':f'mapped_tree_point_{oid}'})
out={'source_timestamp':source['osm3s']['timestamp_osm_base'],'note':'Woodland boundaries and tree-row/point locations from OSM; individual trees within woodland and all crown dimensions are illustrative. Ground raster may contain vegetation height.','woodland_area_m2':forest.area,'trees':points}
(root/'vegetation_points.json').write_text(json.dumps(out,separators=(',',':')),encoding='utf-8')
assert len(points)>500 and forest.area>100000
print('VEGETATION',len(points),'trees; woodland clearance area',round(forest.area),flush=True)

# Keep source terrain untouched; this separate display grid approximates engineered platforms.
grid=np.load(root/'terrain.npz');raw=grid['elevation'];xs,ys=grid['x'],grid['y'];p=np.pad(raw,1,mode='edge')
base=sum(p[j:j+raw.shape[0],i:i+raw.shape[1]] for i in range(3) for j in range(3))/9
display=base.copy();levels={};pads=[]
def platform(g,level,margin,feather):
    if g.is_empty:return
    xmin,ymin,xmax,ymax=g.bounds
    ci=np.where((xs>=xmin-margin-feather)&(xs<=xmax+margin+feather))[0];ri=np.where((ys>=ymin-margin-feather)&(ys<=ymax+margin+feather))[0]
    if not len(ci) or not len(ri):return
    xx,yy=np.meshgrid(xs[ci],ys[ri]);inner=g.buffer(margin)
    from shapely import points,distance
    dist=distance(inner,points(xx,yy));w=np.clip(1-dist/feather,0,1)
    ix=np.ix_(ri,ci);display[ix]=display[ix]*(1-w)+level*w
for f in features:
    if f['kind'] not in ('sport','water'):continue
    g=shape(f['geometry'])
    if g.geom_type not in ('Polygon','MultiPolygon') or g.area<20:continue
    x0,y0,x1,y1=g.bounds;ci=np.where((xs>=x0)&(xs<=x1))[0];ri=np.where((ys>=y0)&(ys<=y1))[0]
    if not len(ci) or not len(ri):continue
    xx,yy=np.meshgrid(xs[ci],ys[ri]);mask=contains_xy(g,xx,yy)
    if not mask.any():continue
    level=float(np.median(base[np.ix_(ri,ci)][mask]));platform(g,level,1.5,5)
    levels[str(f['id'])]=level
inventory={int(i['osm_id']):i for i in json.loads((root/'building_inventory.json').read_text('utf-8'))}
for f in features:
    if f['kind']!='building':continue
    level=inventory[f['id']]['base_elevation_m'];platform(shape(f['geometry']),level,1.8,6)
    pads.append(f['id'])
np.savez_compressed(root/'terrain_refined_display.npz',elevation=display,x=xs,y=ys)
(root/'platforms.json').write_text(json.dumps({'note':'Illustrative platform leveling for visual refinement, not surveyed earthworks. Source DTM retained unchanged.','sports_water_levels':levels,'building_pad_ids':pads}),encoding='utf-8')
print('DISPLAY_PLATFORMS',len(pads),len(levels),'max adjustment',float(np.max(np.abs(display-base))),flush=True)
