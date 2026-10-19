"""Decode bounded official B3DM sample and native CEDD rasters into local reference JSON.
Run with bundled Python 3.12; original source models are never modified.
"""
import hashlib, io, json, struct, sys, urllib.parse, urllib.request, zipfile
from pathlib import Path
sys.path.insert(0,'C:/Users/Amadeus/.agent-reach/cuhk/python')
import numpy as np
import shapely
from shapely.geometry import shape, Polygon, box
from pyproj import Transformer
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
CACHE=Path('C:/Users/Amadeus/.agent-reach/cuhk/calibration_20260928')
OLD=Path('C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922')
OUT=ROOT.parents[1]/'cuhk-campus-web/public/calibration';OUT.mkdir(parents=True,exist_ok=True)
ecef_geog=Transformer.from_crs(4978,4979,always_xy=True)
geog_grid=Transformer.from_crs(4326,2326,always_xy=True)
grid_geog=Transformer.from_crs(2326,4326,always_xy=True)
foot=shape(next(f for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'] if f['id']==107139044)['geometry'])

def controls():
    target=CACHE/'vertical_controls.json'
    if target.exists():return json.loads(target.read_text('utf-8'))
    rows=[]
    for e,n in [(839380,830950),(839580,830950),(839380,831150),(839580,831150),(839480,831050)]:
        lon,lat=grid_geog.transform(e,n)
        url='https://www.geodetic.gov.hk/transform/v2/?'+urllib.parse.urlencode({'inSys':'wgsgeog','outSys':'hkgrid','lat':f'{lat:.11f}','long':f'{lon:.11f}','h':100})
        data=json.load(urllib.request.urlopen(url,timeout=20))
        assert all(k in data for k in ['hkE','hkN','hkpd']),data
        rows.append({'inputE':e,'inputN':n,'lon':lon,'lat':lat,'ellipsoidalHeight':100,'result':data,'url':url})
    target.write_text(json.dumps(rows,indent=2),'utf-8');return rows

control=controls()
A=np.array([[r['inputE']-839400,r['inputN']-831150,1] for r in control[:4]])
coeff=np.linalg.lstsq(A,[r['result']['hkpd']-100 for r in control[:4]],rcond=None)[0]
center=control[4];center_error=float(np.array([80,-100,1])@coeff-(center['result']['hkpd']-100))
assert abs(center_error)<.01

def decode(rec):
    blob=Path(rec['source']['file']).read_bytes();head=struct.unpack('<4s6I',blob[:28]);assert head[0]==b'b3dm'
    fj,fb,bj,bb=head[3:];batch=json.loads(blob[28+fj+fb:28+fj+fb+bj]);g=blob[28+fj+fb+bj+bb:]
    jlen=struct.unpack_from('<I',g,12)[0];doc=json.loads(g[20:20+jlen]);binary=g[28+jlen:]
    names=batch['extensions']['3DTILES_batch_table_hierarchy']['classes'][0]['instances']['names']
    def accessor(index):
        a=doc['accessors'][index];v=doc['bufferViews'][a['bufferView']];dt=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']]);size={'SCALAR':1,'VEC3':3,'VEC2':2}[a['type']]
        return np.ndarray((a['count'],size),dtype=dt,buffer=binary,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride') or dt.itemsize*size,dt.itemsize)).copy()
    transform=np.array(rec['transform']).reshape(4,4,order='F')
    def node(index,parent):
        nd=doc['nodes'][index]
        assert not any(k in nd for k in ['rotation','translation','scale']), 'unexpected TRS needs explicit decoding'
        mat=parent@np.array(nd.get('matrix',np.eye(4).flatten(order='F'))).reshape(4,4,order='F')
        if 'mesh' in nd:
            for p in doc['meshes'][nd['mesh']]['primitives']:
                pos=accessor(p['attributes']['POSITION']).astype(float);v=pos@mat[:3,:3].T+mat[:3,3]
                v=v[:,[0,2,1]]*np.array([1,-1,1])  # glTF Y up -> 3D Tiles Z up
                ecef=v@transform[:3,:3].T+transform[:3,3]
                lon,lat,h=ecef_geog.transform(*ecef.T);e,n=geog_grid.transform(lon,lat)
                x=np.array(e)-839400;y=np.array(n)-831150;z=np.array(h)+coeff[0]*x+coeff[1]*y+coeff[2]
                positions=np.column_stack([x,z,-y]);indices=accessor(p['indices']).reshape(-1,3);batchids=accessor(p['attributes']['_BATCHID']).ravel()
                for bid in np.unique(batchids):
                    faces=indices[np.all(batchids[indices]==bid,axis=1)]
                    if len(faces):yield names[int(bid)],positions,faces,rec['source']['url']
        for child in nd.get('children',[]):yield from node(child,mat)
    for ni in doc['scenes'][doc.get('scene',0)]['nodes']:yield from node(ni,np.eye(4))

groups={}
manifest=json.loads((CACHE/'manifest.json').read_text('utf-8'))
for rec in manifest['leaves']:
    for name,pos,faces,url in decode(rec):
        row=groups.setdefault(name,{'positions':[],'faces':[],'sources':[]})
        used=np.unique(faces);mapping=np.full(len(pos),-1);mapping[used]=np.arange(len(used))+len(row['positions'])
        row['faces'].extend(mapping[faces].tolist());row['positions'].extend(pos[used].tolist());row['sources'].append(url)

candidates=[]
for name,row in groups.items():
    pos=np.array(row['positions']);faces=np.array(row['faces']);tri=pos[faces][:,:,[0,2]]*np.array([1,-1])
    polys=shapely.polygons(tri);polys=polys[shapely.area(polys)>.001];outline=shapely.union_all(polys)
    row['outline']=outline
    iou=foot.intersection(outline).area/foot.union(outline).area
    candidates.append({'id':name,'iou':iou,'area':outline.area,'centroid':[outline.centroid.x,outline.centroid.y],'height':[pos[:,1].min(),pos[:,1].max()],'triangles':len(faces)})
candidates.sort(key=lambda r:r['iou'],reverse=True)
(ROOT/'calibration/candidate_buildings.json').write_text(json.dumps(candidates,indent=2),'utf-8')
print('TOP CANDIDATES',json.dumps(candidates[:7],indent=2))
(CACHE/'decoded_groups.json').write_text(json.dumps({k:{a:b for a,b in v.items() if a!='outline'} for k,v in groups.items()}),'utf-8')
print('CONTROL',coeff,'CENTER ERROR',center_error)

chosen=candidates[0];assert chosen['iou']>.8 and candidates[1]['iou']<.05
official=groups[chosen['id']];reference=official['outline'];pos=np.array(official['positions']);faces=np.array(official['faces'])
shift=coeff[0]*pos[:,0]-coeff[1]*pos[:,2]+coeff[2]
raw=pos[:,1]-shift
scope=box(0,-155,160,-40)
xs=np.arange(.25,160,1);ys=np.arange(-40.25,-155,-1);X,Y=np.meshgrid(xs,ys)
terrain_manifest=json.loads((OLD/'terrain_verified_manifest.json').read_text('utf-8'))
rasters={};source_rasters=[]
for kind in ['dtm','dsm']:
    z=np.full(X.shape,np.nan,dtype=np.float32)
    for row in terrain_manifest:
        if row['kind']!=kind:continue
        e0,n0,e1,n1=row['bbox_hk1980'];ix=np.flatnonzero((xs+839400>=e0)&(xs+839400<e1));iy=np.flatnonzero((ys+831150>=n0)&(ys+831150<n1))
        if not len(ix) or not len(iy):continue
        with zipfile.ZipFile(row['file']) as archive:
            assert archive.testzip() is None
            with Image.open(io.BytesIO(archive.read(row['inner_file']))) as im:arr=np.array(im)
        cols=np.floor((xs[ix]+839400-e0)/.5).astype(int);rows=np.floor((n1-ys[iy]-831150)/.5).astype(int)
        z[np.ix_(iy,ix)]=arr[np.ix_(rows,cols)]
        source_rasters.append({k:row[k] for k in ['kind','url','inner_file','bbox_hk1980','pixel_size_m']})
    assert np.isfinite(z).all() and np.min(z)>-9998
    rasters[kind]=z

def quantiles(vals):
    return dict(zip(['min','p05','median','p95','max'],np.round(np.quantile(vals,[0,.05,.5,.95,1]),4).tolist()))

current=np.load(ROOT/'audits/terrain_shaw_science_corrected_1m.npz')
current={k:current[k] for k in current.files}
if current['y'][0]>current['y'][-1]:
    current['y']=current['y'][::-1];current['elevation']=current['elevation'][::-1]
ix=np.clip(np.searchsorted(current['x'],xs),1,len(current['x'])-1);iy=np.clip(np.searchsorted(current['y'],ys),1,len(current['y'])-1)
assert np.all(np.diff(current['y'])>0)
# Bilinear evaluation of the preserved 1 m display terrain grid, explicitly not a live GLB raycast.
wx=(xs-current['x'][ix-1])/(current['x'][ix]-current['x'][ix-1]);wy=(ys-current['y'][iy-1])/(current['y'][iy]-current['y'][iy-1])
elev=current['elevation'];lower=elev[np.ix_(iy-1,ix-1)]*(1-wx)+elev[np.ix_(iy-1,ix)]*wx
upper=elev[np.ix_(iy,ix-1)]*(1-wx)+elev[np.ix_(iy,ix)]*wx
display=lower*(1-wy[:,None])+upper*wy[:,None]
outside=~shapely.contains_xy(foot.buffer(3),X,Y)
terrain_delta=display-rasters['dtm']

road_data=np.load(ROOT/'road_mesh_v3.npz');rv=road_data['vertices'];rf=road_data['faces'];roads=json.loads((ROOT/'road_mesh_v3.json').read_text('utf-8'))
road_near=[];road_shapes=[]
for row in roads:
    verts=rv[row['vertex_start']:row['vertex_start']+row['vertex_count']];fs=rf[row['face_start']:row['face_start']+row['face_count']]
    if not len(fs):continue
    triangles=verts[fs];centers=triangles.mean(axis=1);mask=shapely.contains_xy(scope,centers[:,0],centers[:,1])
    if not mask.any():continue
    cc=centers[mask];ci=np.floor((cc[:,0]-.25)).astype(int).clip(0,len(xs)-1);cj=np.floor((-40.25-cc[:,1])).astype(int).clip(0,len(ys)-1)
    dtm=rasters['dtm'][cj,ci];poly=shapely.union_all(shapely.polygons(triangles[mask,:,:2]));road_shapes.append(poly)
    road_near.append({'id':row['id'],'name':row['name'],'sampleTriangles':int(mask.sum()),'modelTopMinusDtmM':quantiles(cc[:,2]-dtm),'distanceToCurrentFootprintM':round(poly.distance(foot),3),'distanceToOfficialProjectionM':round(poly.distance(reference),3)})
road_area=shapely.union_all(road_shapes)
ungraded=outside&~shapely.contains_xy(road_area.buffer(3),X,Y)
roof_mask=shapely.contains_xy(foot.buffer(-2),X,Y)
roof_values=rasters['dsm'][roof_mask & (rasters['dsm']>111.3)&(rasters['dsm']<111.9)]
assert len(roof_values)>500
centroid_delta=[reference.centroid.x-foot.centroid.x,reference.centroid.y-foot.centroid.y]
model_building=next(b for b in json.loads((ROOT.parents[1]/'cuhk-campus-web/public/model/buildings.json').read_text('utf-8')) if b['id']=='107139044')
model_bounds={'min':(np.array(model_building['position'])-np.array(model_building['size'])/2).tolist(),'max':(np.array(model_building['position'])+np.array(model_building['size'])/2).tolist()}

metrics={
 'matching':{'sourceId':chosen['id'],'method':'Highest intersection-over-union of XY union of projected official triangles against existing OSM building footprint. Next candidate IoU < 0.013; no name or nearest-center guess.','confidence':'high geometric identity, no official university-name attribute'},
 'footprint':{'currentAreaM2':foot.area,'officialProjectedAreaM2':reference.area,'intersectionOverUnion':chosen['iou'],'centroidOffsetEastNorthM':centroid_delta,'centroidOffsetM':float(np.linalg.norm(centroid_delta)),'symmetricHausdorffM':foot.hausdorff_distance(reference),'boundaryDistanceMedianM':float(np.median([reference.boundary.distance(foot.boundary.interpolate(d)) for d in np.arange(0,foot.length,.5)])),'note':'Reference is full projected building geometry, including overhangs; current comparison is OSM shell footprint, not legal/cadastral footprint. Centroid delta includes shape difference, not a recommended rigid translation.'},
 'height':{'modelMainRoofHKPDM':111.6,'modelEquipmentTopHKPDM':117.6,'officialFlatTopIfECEFEllipsoidConvertedToHKPDM':float(pos[:,1].max()),'officialFlatTopRawEllipsoidM':float(raw.max()),'modelMinusConvertedReferenceRoofM':111.6-float(pos[:,1].max()),'datumAmbiguityM':float(np.median(shift)),'CEDDMainRoofM':quantiles(roof_values),'CEDDStatus':'2020 LiDAR DSM already used by current model correction; not independent proof.','officialRoofStatus':'Uniform flat top. Does not resolve end equipment and stepped roof; vertical semantic of API source not explicitly stated beyond WGS84.'},
 'terrain':{'sampleBoundsLocalEastNorthM':[0,-155,160,-40],'displayMinusDtmOutsideFootprint3mM':quantiles(terrain_delta[outside]),'displayMinusDtmOutsideFootprintAndRoads3mM':quantiles(terrain_delta[ungraded]),'samplesOutsideFootprintAndRoads':int(ungraded.sum()),'method':'Current preserved 1m terrain grid bilinear heights vs native 0.5m DTM center values sampled every1m; excludes building +3m, separately roads+3m. DTM under buildings is interpolated bare earth, not ground floor.'},
 'roads':{'rows':road_near,'method':'Existing road triangle centers vs nearest 1m subset of native DTM, scoped to sample. Difference may indicate constructed grade, bridge, retaining works or epoch; not automatic road error. Distances use horizontal road-top triangle union.'},
 'correctionApplied':False,'decision':'Retain existing Blender and local detailed building. Flag footprint edges, terrace/road grading and vertical datum ambiguity for field/photo checks; no blind resize, translation or terrain reset.'}

compact=lambda a:np.round(a,4).reshape(-1).tolist()
tx=X[::2,::2];ty=Y[::2,::2];tz=rasters['dtm'][::2,::2];terrain_positions=np.stack([tx,tz,-ty],axis=-1).reshape(-1,3)
w=tx.shape[1];h=tx.shape[0];terrain_faces=[]
for j in range(h-1):
    for i in range(w-1):
        a=j*w+i;terrain_faces.extend([a,a+w,a+1,a+1,a+w,a+w+1])
# DSM remains a point surface, not a made-up watertight building model.
dsm_positions=np.stack([X,rasters['dsm'],-Y],axis=-1).reshape(-1,3)
data={
 'title':'政府公开三维数据参考层','sample':'逸夫科学大楼及周边 160 × 115 m','verifiedAt':'2026-09-28','defaultVisible':False,
 'view':{'position':[255,220,310],'target':[80,99,95]},
 'summary':[
  '青色：LandsD 官方建筑壳体；土色：CEDD DTM；橙点：CEDD DSM。',
  f"轮廓重叠率 {chosen['iou']*100:.1f}%；投影质心差 {np.linalg.norm(centroid_delta):.2f} m（含形状差，非平移建议）。",
  f"现有主屋顶 111.60 m；参考换算值 {pos[:,1].max():.2f} m HKPD。",
  f"源高程垂直语义待核：不作垂直换算时 {raw.max():.2f} m，差约 {np.median(shift):.2f} m。",
  '官方壳体为统一平顶，未表达现有两端设备结构；保留细化主模型。',
  f"建筑/道路外地面差中位数 {np.median(terrain_delta[ungraded]):+.2f} m（显示地形−DTM，含人工整坡）。",
  '黄色框：当前建筑；蓝色框：参考壳体。未应用任何主模型修改。'],
 'coordinateSystem':{'terrainHorizontal':'EPSG:2326 Hong Kong 1980 Grid','terrainVertical':'HKPD (EPSG:5738)','officialInput':'3D Tiles WGS84 / ECEF, glTF Y-up','worldUnits':'metre','originHK1980':[839400,831150,0],'formula':'Three = [E-839400, HKPD, -(N-831150)]','localScale':1,'localRotationFromBlenderDegrees':[-90,0,0],'localTranslation':[0,0,0],'manualAlignment':None,'sourceHeightConversion':{'method':'Official geodetic API at four sample corners, linear plane of HKPD minus WGS84 ellipsoidal height; center independently checked. This assumes ECEF source altitude is ellipsoidal and remains explicitly switchable because source vertical semantics are not documented.','coefficientsOnLocalEastNorth':[float(c) for c in coeff],'centerResidualM':center_error,'controls':control,'horizontalPipeline':geog_grid.description,'maximumControlXYDifferenceM':max(float(np.hypot(r['result']['hkE']-r['inputE'],r['result']['hkN']-r['inputN'])) for r in control)}},
 'sources':{'governmentBuilding':{'owner':'香港特别行政区政府地政总署','documentation':'https://portal.csdi.gov.hk/csdi-webpage/apidoc/3d-spatial-data-api','acquiredAt':'2026-09-28','epoch':None,'epochNote':'tilesetVersion1.2.3 is a format/version identifier; no survey/imagery acquisition date provided for this component.','componentId':chosen['id'],'leafUrls':sorted(set(official['sources'])),'rootTransformECEF':manifest['leaves'][0]['transform'],'selection':'4 JSON indices +14 bounded leaves, 434473 bytes total offline; only matched building is shipped.'},'cedd':{'owner':'香港特别行政区政府土木工程拓展署','documentation':'https://www.ginfo.cedd.gov.hk/geoopendata/eng/LIDAR.aspx','metadata':'https://www.ginfo.cedd.gov.hk/geoopendata/Data/LiDAR/2020%20LiDAR.xml','acquiredAt':'2026-09-22','verifiedAt':'2026-09-28','epoch':'2019-12-19 to2020-02-01 (2020 survey metadata)','nativePixelM':.5,'renderDtmSpacingM':2,'renderDsmSpacingM':1,'verticalAccuracyM':None,'rasters':source_rasters},'attribution':'© 香港特别行政区政府地政总署 / 土木工程拓展署；现有校园轮廓 © OpenStreetMap contributors (ODbL).'},
 'modelBounds':model_bounds,'metrics':metrics,
 'building':{'positions':compact(pos),'indices':faces.ravel().tolist(),'heightShift':compact(shift)},
 'terrain':{'positions':compact(terrain_positions),'indices':terrain_faces},
 'dsm':{'positions':compact(dsm_positions)}
}
assert np.all(np.isfinite(pos)) and len(data['building']['indices'])%3==0
assert max(data['building']['indices'])<len(pos)
assert np.max(np.abs(pos[:,[0,2]]))<200 and np.max(pos[:,1])<200
assert data['coordinateSystem']['sourceHeightConversion']['maximumControlXYDifferenceM']<.05
outpath=OUT/'shaw-reference.json';outpath.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),'utf-8')
assert outpath.stat().st_size<1_500_000
(ROOT/'calibration/geometry-differences.json').write_text(json.dumps(metrics,ensure_ascii=False,indent=2),'utf-8')
(ROOT/'calibration/source-and-coordinate.json').write_text(json.dumps({k:data[k] for k in ['coordinateSystem','sources']},ensure_ascii=False,indent=2),'utf-8')
print('OUTPUT',outpath.stat().st_size,'BYTES',len(terrain_faces)//3,'DTM TRIANGLES',len(dsm_positions),'DSM POINTS')
print(json.dumps({k:v for k,v in metrics.items() if k!='roads'},ensure_ascii=False,indent=2))
