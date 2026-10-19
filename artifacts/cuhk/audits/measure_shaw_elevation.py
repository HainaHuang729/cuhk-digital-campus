"""Read-only comparison of Shaw Science Building against cached 2020 LiDAR."""
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, 'C:/Users/Amadeus/.agent-reach/cuhk/python')
import numpy as np
from PIL import Image
from shapely.geometry import shape
from shapely import contains_xy

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path('C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922')
record = next(f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'] if f['id'] == 107139044)
foot = shape(record['geometry'])
x0,y0,x1,y1 = foot.bounds
xs = np.arange(np.floor(x0-25)+.25, np.ceil(x1+25), .5)
ys = np.arange(np.ceil(y1+25)-.25, np.floor(y0-25), -.5)
X,Y = np.meshgrid(xs,ys)
manifest = json.loads((CACHE/'terrain_verified_manifest.json').read_text('utf-8'))
rasters = {}; sources = {}
for kind in ('dtm','dsm'):
    z = np.full(X.shape,np.nan,dtype=np.float32); used=[]
    for rec in manifest:
        if rec['kind'] != kind: continue
        e0,n0,e1,n1 = rec['bbox_hk1980']
        ix=np.flatnonzero((xs+839400>=e0)&(xs+839400<e1)); iy=np.flatnonzero((ys+831150>=n0)&(ys+831150<n1))
        if not len(ix) or not len(iy): continue
        with zipfile.ZipFile(rec['file']) as archive:
            with Image.open(io.BytesIO(archive.read(rec['inner_file']))) as im: arr=np.array(im)
        cols=np.floor((xs[ix]+839400-e0)/.5).astype(int); rows=np.floor((n1-ys[iy]-831150)/.5).astype(int)
        vals=arr[np.ix_(rows,cols)]; vals=np.where(vals<=-9998,np.nan,vals)
        z[np.ix_(iy,ix)]=vals; used.append(rec['file'])
    rasters[kind]=z; sources[kind]=used

def stats(values):
    valid = values[np.isfinite(values)]
    return {'samples':int(values.size),'valid':int(valid.size),'quantiles_hkpd_m':dict(zip(['min','p05','p10','p25','p50','p75','p90','p95','max'],np.quantile(valid,[0,.05,.1,.25,.5,.75,.9,.95,1]).round(4).tolist()))} if valid.size else {'samples':int(values.size),'valid':0}

masks = {'footprint':contains_xy(foot,X,Y),'inner_2m':contains_xy(foot.buffer(-2),X,Y),'outside_0_3m':contains_xy(foot.buffer(3),X,Y)&~contains_xy(foot,X,Y),'outside_3_10m':contains_xy(foot.buffer(10),X,Y)&~contains_xy(foot.buffer(3),X,Y)}
out={'building':record,'source':'CEDD 2020 LiDAR DSM/DTM, native 0.5m raster centers','crs':'EPSG:2326','vertical_datum':'HKPD','local_origin':[839400,831150,0],'sources':sources,'regions':{},'cells_10m':[],'edges':[]}
for name,mask in masks.items():
    out['regions'][name]={kind:stats(z[mask]) for kind,z in rasters.items()}
    out['regions'][name]['dsm_minus_dtm']=stats((rasters['dsm']-rasters['dtm'])[mask])
for a in np.arange(np.floor(x0/10)*10,x1,10):
    for b in np.arange(np.floor(y0/10)*10,y1,10):
        mask=masks['inner_2m']&(X>=a)&(X<a+10)&(Y>=b)&(Y<b+10)
        if mask.sum()<8: continue
        out['cells_10m'].append({'x':float(a),'y':float(b),'dsm':stats(rasters['dsm'][mask]),'dtm':stats(rasters['dtm'][mask])})
coords=list(foot.exterior.coords)
from shapely.geometry import LineString
for index,(a,b) in enumerate(zip(coords[:-1],coords[1:])):
    line=LineString([a,b])
    if line.length<7: continue
    mask=contains_xy(line.buffer(3),X,Y)&~masks['footprint']
    out['edges'].append({'index':index,'start':a,'end':b,'length':line.length,'outside_dtm':stats(rasters['dtm'][mask]),'outside_dsm':stats(rasters['dsm'][mask])})
for fn in ['terrain_survey_1m.npz','terrain_sports_leveled_1m.npz']:
    data=np.load(ROOT/fn); xx,yy=np.meshgrid(data['x'],data['y']); mask=contains_xy(foot,xx,yy)
    out[fn]={'keys':list(data.keys()),'footprint':stats(data['elevation'][mask])}
    if fn=='terrain_sports_leveled_1m.npz':
        ix=np.argmin(np.abs(xs[:,None]-data['x'][None,:]),axis=1);iy=np.argmin(np.abs(ys[:,None]-data['y'][None,:]),axis=1)
        current=data['elevation'][np.ix_(iy,ix)]
        for row in out['edges']:
            line=LineString([row['start'],row['end']]);edge_mask=contains_xy(line.buffer(3),X,Y)&~masks['footprint']
            row['current_display_ground_nearest_1m']=stats(current[edge_mask])

plateau=masks['inner_2m']&(rasters['dsm']>111.3)&(rasters['dsm']<111.9)
plane=np.linalg.lstsq(np.column_stack([X[plateau],Y[plateau],np.ones(plateau.sum())]),rasters['dsm'][plateau],rcond=None)[0]
residual=rasters['dsm'][plateau]-(plane[0]*X[plateau]+plane[1]*Y[plateau]+plane[2])
out['main_roof_plateau']={'selector_hkpd_m':[111.3,111.9],'stats':stats(rasters['dsm'][plateau]),'plane_z_ax_by_c':plane.tolist(),'residual_rms_m':float(np.sqrt(np.mean(residual**2))),'note':'Height-range selection identifies dominant roof slab, excludes taller plant and lower edge/ground returns. Fitted plane is diagnostic, not a survey tolerance.'}
for name,region in [('west_end',X<50),('east_end',X>110),('center',((X>=50)&(X<=110)))]:
    mask=masks['inner_2m']&region&(rasters['dsm']>115)
    out[name+'_raised_roof']=stats(rasters['dsm'][mask])

assert out['regions']['inner_2m']['dsm']['valid'] > 1000
np.savez_compressed(Path(__file__).with_name('shaw_elevation_samples.npz'),x=xs,y=ys,dtm=rasters['dtm'],dsm=rasters['dsm'],footprint=masks['footprint'])
Path(__file__).with_name('shaw_elevation_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),'utf-8')
from PIL import ImageDraw,ImageFont
canvas=Image.new('RGB',(1920,760),'white');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
palette=np.array([[68,1,84],[59,82,139],[33,145,140],[94,201,98],[253,231,37]])
def colorize(z,limits):
    scaled=np.nan_to_num(np.clip((z-limits[0])/(limits[1]-limits[0]),0,1))*4
    low=np.minimum(scaled.astype(int),3);frac=scaled-low
    return ((1-frac[...,None])*palette[low]+frac[...,None]*palette[low+1]).astype('uint8')
draw.text((20,10),'Run Run Shaw Science Building | Red = OSM footprint | Native 0.5 m LiDAR pixels | North is up',fill='black',font=font)
for panel,(title,z,limits) in enumerate([('Bare earth / DTM (2020)',rasters['dtm'],(65,120)),('Top surface / DSM (2020)',rasters['dsm'],(65,120)),('Roof detail / DSM (2020)',rasters['dsm'],(110,119))]):
    image=Image.fromarray(colorize(z,limits));width=600;height=round(image.height*width/image.width);ox=panel*640+20;oy=95
    canvas.paste(image.resize((width,height)),(ox,oy))
    coords_px=[(ox+(x-(xs[0]-.25))/(len(xs)*.5)*width,oy+((ys[0]+.25)-y)/(len(ys)*.5)*height) for x,y in foot.exterior.coords]
    draw.line(coords_px,fill='red',width=2);draw.text((ox,55),title,fill='black',font=font)
    bar=Image.fromarray(colorize(np.linspace(limits[0],limits[1],600)[None,:],limits)).resize((600,20));canvas.paste(bar,(ox,oy+height+20))
    draw.text((ox,oy+height+48),str(limits[0])+' m HKPD',fill='black',font=font);draw.text((ox+460,oy+height+48),str(limits[1])+' m HKPD',fill='black',font=font)
canvas.save(Path(__file__).with_name('shaw_elevation_diagnostics.png'))
print(json.dumps({k:v for k,v in out.items() if k not in ('building','cells_10m','edges')},ensure_ascii=False,indent=2))
