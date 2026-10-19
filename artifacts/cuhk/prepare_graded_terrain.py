"""Prepare a 1m display terrain from official 0.5m DTM, with existing site pads."""
import io,json,sys,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parent
CACHE=Path('C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922')
sys.path.insert(0,str(CACHE.parent/'python'))
from scipy.ndimage import map_coordinates,distance_transform_edt,gaussian_filter
from shapely.geometry import shape
from shapely import points,distance,contains_xy

xs=np.arange(-1200,1201,dtype=float);ys=xs[::-1].copy()
z=np.full((len(ys),len(xs)),np.nan,dtype=np.float32)
# Official TIFF values are pixel-centred. Bilinear sampling explicitly accounts
# for the half-pixel rather than treating a TIFF corner as a terrain sample.
used=[]
for rec in json.loads((CACHE/'terrain_verified_manifest.json').read_text('utf-8')):
    if rec['kind']!='dtm':continue
    e0,n0,e1,n1=rec['bbox_hk1980'];ex=xs+839400;ny=ys+831150
    ix=np.flatnonzero((ex>=e0)&(ex<e1));iy=np.flatnonzero((ny>=n0)&(ny<n1))
    if not len(ix) or not len(iy):continue
    with zipfile.ZipFile(rec['file']) as a:
        with Image.open(io.BytesIO(a.read(rec['inner_file']))) as im:arr=np.asarray(im,dtype=float)
    rr,cc=np.meshgrid((n1-ny[iy])/.5-.5,(ex[ix]-e0)/.5-.5,indexing='ij')
    arr[arr<=-9998]=np.nan
    z[np.ix_(iy,ix)]=map_coordinates(arr,[rr,cc],order=1,mode='nearest')
    used.append(rec['file'])
missing=~np.isfinite(z)
if missing.any():
    fallback=np.load(ROOT/'terrain.npz')
    rr,cc=np.meshgrid((fallback['y'][0]-ys)/5,(xs-fallback['x'][0])/5,indexing='ij')
    legacy=map_coordinates(fallback['elevation'],[rr,cc],order=1,mode='nearest')
    z[missing]=legacy[missing]
assert np.isfinite(z).all()
np.savez_compressed(ROOT/'terrain_survey_1m.npz',x=xs,y=ys,elevation=z,source_valid=~missing)
old=np.load(ROOT/'terrain_refined_display.npz');oldz=old['elevation']
out=z.astype(float).copy();blend=np.zeros(z.shape,dtype=float)
features=json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']
inventory={str(b['osm_id']):b for b in json.loads((ROOT/'building_inventory.json').read_text('utf-8'))}
alignments=[]
pad_count=0
for f in features:
    if f['kind'] not in ('building','sport','water'):continue
    if f['geometry']['type'] not in ('Polygon','MultiPolygon'):continue
    g=shape(f['geometry']);x0,y0,x1,y1=g.bounds
    # Sport/water pads retain their current levels; buildings are aligned after
    # that pass to the finer DTM rather than preserving a canopy-height plateau.
    if f['kind']=='building':continue
    ix=np.flatnonzero((xs>=x0-10)&(xs<=x1+10));iy=np.flatnonzero((ys>=y0-10)&(ys<=y1+10))
    if not len(ix) or not len(iy):continue
    xx,yy=np.meshgrid(xs[ix],ys[iy]);d=distance(points(xx,yy),g)
    weight=np.clip((10-d)/8,0,1);weight=weight*weight*(3-2*weight)
    blend[np.ix_(iy,ix)]=np.maximum(blend[np.ix_(iy,ix)],weight);pad_count+=1
rr,cc=np.meshgrid((old['y'][0]-ys)/5,(xs-old['x'][0])/5,indexing='ij')
pad=map_coordinates(oldz,[rr,cc],order=1,mode='nearest')
out=out*(1-blend)+pad*blend
for f in features:
    if f['kind']!='building':continue
    g=shape(f['geometry']);x0,y0,x1,y1=g.bounds
    ix=np.flatnonzero((xs>=x0-10)&(xs<=x1+10));iy=np.flatnonzero((ys>=y0-10)&(ys<=y1+10))
    if not len(ix) or not len(iy):continue
    xx,yy=np.meshgrid(xs[ix],ys[iy]);inside=contains_xy(g,xx,yy);valid=inside&~missing[np.ix_(iy,ix)]
    oid=str(f['id']);oldlevel=inventory[oid]['base_elevation_m'];coverage=valid.sum()/max(1,inside.sum())
    # Same lower-quartile base convention as the original model, now using
    # dense bare-earth samples. It is an alignment estimate, not a measured FFL.
    newlevel=float(np.percentile(z[np.ix_(iy,ix)][valid],25)) if valid.sum()>=8 and coverage>.8 else oldlevel
    if abs(newlevel-oldlevel)<.25:newlevel=oldlevel
    d=distance(points(xx,yy),g);weight=np.clip((10-d)/8,0,1);weight=weight*weight*(3-2*weight)
    current=out[np.ix_(iy,ix)];out[np.ix_(iy,ix)]=current*(1-weight)+(newlevel-.25)*weight
    alignments.append({'osm_id':oid,'name':inventory[oid]['name'],'old_base_m':oldlevel,'new_base_m':newlevel,'vertical_shift_m':newlevel-oldlevel,'valid_source_fraction':float(coverage),'source_sample_count':int(valid.sum()),'method':'25th percentile of valid 1m DTM samples inside OSM footprint; legacy fallback if insufficient coverage'})
np.savez_compressed(ROOT/'terrain_platforms_1m.npz',x=xs,y=ys,elevation=out.astype(np.float32))
(ROOT/'building_terrain_alignment.json').write_text(json.dumps(alignments,ensure_ascii=False,indent=2),encoding='utf-8')
report={'source':'CEDD 2020 LiDAR-derived 0.5m DTM','display_sample_interval_m':1,'shape':list(z.shape),'source_archives':used,'source_nodata_legacy_fallback_samples':int(missing.sum()),'existing_sport_water_pad_count':pad_count,'aligned_building_count':sum(abs(a['vertical_shift_m'])>.01 for a in alignments),'pad_blend_samples':int(np.sum(blend>0)),'vertical_datum':'HKPD','crs':'EPSG:2326','origin':[839400,831150,0],'note':'1m display sampling derived from 0.5m source. Source NoData (including sea) retains original 5m scene terrain, explicitly masked source_valid=false. Buildings align to lower-quartile bare-earth elevation with local pads; sport/water levels retained. Road bed grading is illustrative, not a new survey.'}
(ROOT/'terrain_1m_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
