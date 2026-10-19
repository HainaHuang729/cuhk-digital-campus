"""Fetch only spatially intersecting 3D Spatial Data leaves; never the whole tileset."""
import json, sys, urllib.request, urllib.parse
from pathlib import Path
sys.path.insert(0, 'C:/Users/Amadeus/.agent-reach/cuhk/python')
import numpy as np
from pyproj import Transformer

CACHE = Path('C:/Users/Amadeus/.agent-reach/cuhk/calibration_20260928')
CACHE.mkdir(exist_ok=True)
ROOT = 'https://data.map.gov.hk/api/3d-data/3dsd/WGS84/building/tileset.json'
KEY = '3967f8f365694e0798af3e7678509421'  # Public example key printed in official API documentation.
point = np.array(Transformer.from_crs(2326, 4978, always_xy=True).transform(839480, 831050, 100))
fetched = []; leaves = []; seen = set()

def retrieve(url):
    if url in seen: raise RuntimeError('cyclic tileset')
    seen.add(url)
    if len(seen)>40: raise RuntimeError('bounded sample request budget exceeded')
    request_url = url + ('&' if '?' in url else '?') + 'key=' + KEY
    path=CACHE/(str(len(fetched)).zfill(2)+'_'+Path(urllib.parse.urlparse(url).path).name)
    with urllib.request.urlopen(request_url, timeout=25) as response:
        blob=response.read(8_000_001)
    if len(blob)>8_000_000: raise RuntimeError('leaf exceeds local sample download budget')
    path.write_bytes(blob)
    fetched.append({'url':url, 'file':str(path), 'bytes':len(blob)})
    print(path.name, len(blob), flush=True)
    return blob

def near(tile, matrix):
    box=tile['boundingVolume'].get('box')
    if box is None: raise RuntimeError('unexpected bounding volume')
    center=(matrix@np.r_[box[:3],1])[:3]
    axes=matrix[:3,:3]@np.array(box[3:]).reshape(3,3).T
    q=np.linalg.solve(axes, point-center)
    lengths=np.linalg.norm(axes,axis=0)
    return bool(np.all(np.abs(q)<=1+95/lengths))

def visit(tile, base, parent=np.eye(4)):
    matrix=parent@np.array(tile.get('transform',np.eye(4).flatten(order='F'))).reshape(4,4,order='F')
    if not near(tile,matrix): return
    children=tile.get('children',[])
    content=tile.get('content',{})
    uri=content.get('uri',content.get('url'))
    # REPLACE parents are coarser duplicates: fetch only child leaves.
    if uri and (not children or uri.endswith('.json')):
        url=urllib.parse.urljoin(base,uri)
        blob=retrieve(url)
        if uri.endswith('.json'):
            data=json.loads(blob); visit(data['root'],url,matrix)
        else: leaves.append({'source':fetched[-1], 'transform':matrix.flatten(order='F').tolist(), 'boundingVolume':tile['boundingVolume']})
    for child in children: visit(child,base,matrix)

if __name__=='__main__':
    root=json.loads(retrieve(ROOT));visit(root['root'],ROOT)
    (CACHE/'manifest.json').write_text(json.dumps({'checkedAt':'2026-09-28','queryEastingNorthing':[839480,831050], 'queryRadiusM':95, 'queryHeightCaveat':'100 m ellipsoidal assumed only for tile selection, not a vertical calibration.', 'fetched':fetched,'leaves':leaves},indent=2),'utf-8')
    print('LEAVES',len(leaves),'BYTES',sum(row['bytes'] for row in fetched))
