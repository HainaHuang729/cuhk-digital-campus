"""Prepare the CUHK geographic crop. Run with bundled Python, numpy, pyproj and shapely."""
import json, sys, zipfile
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent
CACHE = Path.home()/'.agent-reach/cuhk'
sys.path.insert(0, str(CACHE/'python'))
from pyproj import Transformer
from shapely.geometry import Polygon, LineString, box, mapping
from shapely.ops import polygonize, unary_union

tr = Transformer.from_crs(4326, 2326, always_xy=True)
origin = (839400., 831150.)
bounds = (838200., 829950., 840600., 832350.)
clip = box(*bounds)
def coords(g):
    return [tr.transform(p['lon'], p['lat']) for p in g if 'lon' in p]
def relation_polygon(e):
    outer, inner = [], []
    for m in e.get('members', []):
        p = coords(m.get('geometry', []))
        if len(p)>2:
            (inner if m.get('role')=='inner' else outer).append(LineString(p))
    a = unary_union(list(polygonize(unary_union(outer))))
    if inner: a = a.difference(unary_union(list(polygonize(unary_union(inner)))))
    return a

elements = json.loads((CACHE/'osm_full.json').read_text('utf-8'))['elements']
campus = relation_polygon(next(e for e in elements if e['id']==7802779 and e['type']=='relation'))
assert campus.area > 500000, campus.area
print('Campus boundary area', round(campus.area), flush=True)

# ASC rows are north to south. Pixel centres start on integer multiples of five.
with zipfile.ZipFile(CACHE/'dtm.zip') as z:
    with z.open('Whole_HK_DTM_5m.asc') as f:
        hdr = dict(f.readline().decode().split() for _ in range(6))
        nrows, ncols = int(hdr['nrows']), int(hdr['ncols'])
        cell = float(hdr['cellsize'])
        xfirst = float(hdr['xllcorner']) + cell/2
        yfirst = float(hdr['yllcorner']) + cell*(nrows-.5)
        c0, c1 = [round((v-xfirst)/cell) for v in (bounds[0],bounds[2])]
        r0, r1 = [round((yfirst-v)/cell) for v in (bounds[3],bounds[1])]
        rows=[]
        for i,line in enumerate(f):
            if i>r1: break
            if i>=r0: rows.append(np.fromstring(line.decode(),sep=' ')[c0:c1+1])
elev=np.array(rows,dtype=np.float32)
valid=elev!=-9999
elev[~valid]=0
assert elev.shape==(481,481), elev.shape
np.savez_compressed(ROOT/'terrain.npz', elevation=elev, valid=valid,
                    x=np.arange(c0,c1+1)*cell+xfirst-origin[0],
                    y=yfirst-np.arange(r0,r1+1)*cell-origin[1])

records=[]
relation_members={m['ref'] for e in elements if e['type']=='relation' and 'building' in e.get('tags',{}) for m in e.get('members',[]) if m.get('role') in ('outer','inner')}
for e in elements:
    tags=e.get('tags',{})
    kind = 'building' if 'building' in tags else 'road' if 'highway' in tags else 'water' if tags.get('natural')=='water' else 'sport' if tags.get('leisure') in ('pitch','track','swimming_pool') else None
    if kind is None or (e['type']=='way' and e['id'] in relation_members): continue
    if e['type']=='relation': g=relation_polygon(e)
    else:
        pts=coords(e.get('geometry',[]))
        if len(pts)<2: continue
        if kind=='road' or (kind=='sport' and tags.get('leisure')=='track' and tags.get('area')=='no'): g=LineString(pts)
        elif len(pts)>3 and pts[0]==pts[-1]: g=Polygon(pts).buffer(0)
        else: continue
    g=g.intersection(clip)
    if g.is_empty: continue
    inside=campus.buffer(20).intersects(g.centroid)
    # Context buildings immediately outside the mapped campus remain visible in grey.
    if kind=='building' and not inside and g.distance(campus)>160: continue
    from shapely.affinity import translate
    g=translate(g,xoff=-origin[0],yoff=-origin[1])
    records.append(dict(id=e['id'],kind=kind,tags=tags,campus=inside,geometry=mapping(g)))

data=dict(origin_hk1980=origin,bounds_hk1980=bounds,crs='EPSG:2326',vertical_datum='Hong Kong Principal Datum',
          osm_timestamp=json.loads((CACHE/'osm_full.json').read_text('utf-8'))['osm3s']['timestamp_osm_base'],
          campus_boundary=mapping(translate(campus,xoff=-origin[0],yoff=-origin[1])),features=records)
(ROOT/'geodata.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
from collections import Counter
print(Counter(r['kind'] for r in records), 'campus buildings',sum(r['kind']=='building' and r['campus'] for r in records),flush=True)
print('Terrain range',float(elev.min()),float(elev.max()),'valid',float(valid.mean()),flush=True)

# Close the observed coastline against the crop rectangle; the eastern edge lies in Tolo Harbour.
from shapely.geometry import Point
coast=json.loads((CACHE/'coastline.json').read_text('utf-8'))['elements']
segments=[LineString(coords(e['geometry'])).intersection(clip) for e in coast if len(e.get('geometry',[]))>1]
regions=list(polygonize(unary_union([clip.boundary]+segments)))
sea=next((p for p in regions if p.covers(Point(bounds[2]-1,bounds[3]-1))),None)
assert sea is not None and 10000<sea.area<clip.area*.6, [(p.area) for p in regions]
records.append(dict(id=0,kind='sea',tags={'name:en':'Tolo Harbour / mapped coastline'},campus=False,
                    geometry=mapping(translate(sea,xoff=-origin[0],yoff=-origin[1]))))

# Bake planar triangulation here so Blender only needs its built-in numpy.
from shapely.geometry import shape
from shapely import constrained_delaunay_triangles
def triangulated(poly,spacing=None):
    if poly.geom_type=='MultiPolygon':
        return [item for p in poly.geoms for item in triangulated(p,spacing)]
    if poly.geom_type!='Polygon' or poly.area<.5: return []
    vertices=[]; indices={}; faces=[]
    triangles=[list(t.exterior.coords)[:3] for t in constrained_delaunay_triangles(poly).geoms]
    while triangles:
        points=triangles.pop()
        if spacing:
            lengths=[sum((points[i][k]-points[(i+1)%3][k])**2 for k in (0,1)) for i in range(3)]
            i=int(np.argmax(lengths))
            if lengths[i]>spacing**2:
                a,b,c=points[i],points[(i+1)%3],points[(i+2)%3]; mid=((a[0]+b[0])/2,(a[1]+b[1])/2)
                triangles.extend([[a,mid,c],[mid,b,c]]); continue
        face=[]
        for p in points:
            key=tuple(p)
            if key not in indices: indices[key]=len(vertices); vertices.append(key)
            face.append(indices[key])
        faces.append(face)
    rings=[list(poly.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in poly.interiors]
    return [dict(vertices=vertices,faces=faces,rings=rings)]
meshes=[]
for f in records:
    g=shape(f['geometry']); tags=f['tags']
    if f['kind']=='road':
        if tags.get('tunnel')=='yes' or tags.get('highway') in ('proposed','construction'): continue
        hw=tags['highway']
        width={'motorway':10,'motorway_link':6,'trunk':9,'primary':9,'secondary':8,'tertiary':7,'residential':5,'service':4,'unclassified':5,'footway':1.8,'path':1.4,'steps':2,'pedestrian':3,'cycleway':2.5}.get(hw,3)
        try: width=float(tags.get('width',width))
        except ValueError: pass
        g=g.segmentize(6).buffer(width/2,quad_segs=2).intersection(box(-1200,-1200,1200,1200))
    elif f['kind']=='sport' and tags.get('leisure')=='track' and g.geom_type in ('LineString','MultiLineString'):
        g=g.segmentize(6).buffer(4 if tags.get('sport')=='running' else 1.5,quad_segs=3)
    if f['kind']!='building': g=g.segmentize(6)
    parts=triangulated(g,8 if f['kind'] not in ('building','sea') else None)
    if parts: meshes.append({k:v for k,v in f.items() if k!='geometry'} | {'parts':parts})
(ROOT/'meshes.json').write_text(json.dumps(meshes,ensure_ascii=False),encoding='utf-8')
print('Triangulated features',len(meshes),flush=True)
