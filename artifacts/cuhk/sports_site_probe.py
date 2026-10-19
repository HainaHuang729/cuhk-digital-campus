import json,sys,numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
from shapely.geometry import shape,Polygon
from shapely import contains_xy
features=json.loads((ROOT/'geodata.json').read_text('utf-8'))['features']
report=[]
for track in [f for f in features if f['kind']=='sport' and f['tags'].get('sport')=='running']:
    line=shape(track['geometry']);p=Polygon(line.coords);ground=p.buffer(5)
    r={'track_id':track['id'],'inside_sports':[{'id':f['id'],'tags':f['tags']} for f in features if f['kind']=='sport' and f['id']!=track['id'] and p.covers(shape(f['geometry']).representative_point())],'grids':{}}
    for fname in ['terrain_survey_1m.npz','terrain_platforms_1m.npz','terrain_roads_graded_1m.npz','terrain_refined_display.npz']:
        grid=np.load(ROOT/fname);x,y=grid['x'],grid['y'];x0,y0,x1,y1=ground.bounds
        ci=np.flatnonzero((x>x0)&(x<x1));ri=np.flatnonzero((y>y0)&(y<y1));xx,yy=np.meshgrid(x[ci],y[ri]);mask=contains_xy(ground,xx,yy);z=grid['elevation'][np.ix_(ri,ci)][mask]
        r['grids'][fname]={'count':len(z),'quantiles':dict(zip(['min','q05','q25','median','q75','q95','max'],map(float,np.percentile(z,[0,5,25,50,75,95,100]))))}
    report.append(r)
print(json.dumps(report,ensure_ascii=False,indent=2))
(ROOT/'sports_site_probe.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
