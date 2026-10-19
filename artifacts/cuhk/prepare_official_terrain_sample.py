"""Extract native 0.5 m CEDD raster centres around the official building sample."""
import io,json,math,zipfile
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parent
CACHE=Path('C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922')
models=json.loads((ROOT/'official_3d_sample_report.json').read_text('utf-8'))['models']
lo=np.min([m['local_bounds_min'] for m in models],axis=0)
hi=np.max([m['local_bounds_max'] for m in models],axis=0)
emin=math.floor((lo[0]+839400-30)/.5)*.5
emax=math.ceil((hi[0]+839400+30)/.5)*.5
nmin=math.floor((lo[1]+831150-30)/.5)*.5
nmax=math.ceil((hi[1]+831150+30)/.5)*.5
xs=np.arange(emin+.25,emax,.5);ys=np.arange(nmax-.25,nmin,-.5)
z=np.full((len(ys),len(xs)),np.nan,dtype=np.float32);used=[]
for rec in json.loads((CACHE/'terrain_verified_manifest.json').read_text('utf-8')):
    if rec['kind']!='dtm':continue
    e0,n0,e1,n1=rec['bbox_hk1980']
    ix=np.flatnonzero((xs>=e0)&(xs<e1));iy=np.flatnonzero((ys>=n0)&(ys<n1))
    if not len(ix) or not len(iy):continue
    with zipfile.ZipFile(rec['file']) as archive:
        with Image.open(io.BytesIO(archive.read(rec['inner_file']))) as im:
            arr=np.array(im)
    cols=np.floor((xs[ix]-e0)/.5).astype(int);rows=np.floor((n1-ys[iy])/.5).astype(int)
    vals=arr[np.ix_(rows,cols)];vals=np.where(vals<=-9998,np.nan,vals)
    z[np.ix_(iy,ix)]=vals;used.append(rec['file'])
assert np.isfinite(z).all(),'Missing raster samples'
np.savez_compressed(ROOT/'official_terrain_05m_sample.npz',x=xs-839400,y=ys-831150,elevation=z)
report={'source':'CEDD 2020 LiDAR-derived DTM','pixel_spacing_m':.5,'pixel_location':'GeoTIFF pixel centres; no interpolation, grading, or vertical scaling','vertical_datum':'HKPD','horizontal_crs':'EPSG:2326','local_origin':[839400,831150,0],'bbox_hk1980':[emin,nmin,emax,nmax],'shape':list(z.shape),'sample_count':int(z.size),'z_min_m':float(z.min()),'z_max_m':float(z.max()),'source_archives':used,'limitation':'Acquired around 2020; source does not provide a verified vertical accuracy in this task. Building photography and terrain acquisition dates differ.'}
(ROOT/'official_terrain_05m_sample_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
