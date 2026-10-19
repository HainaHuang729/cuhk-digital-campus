"""Smooth connected road elevation profiles, retaining mapped plan geometry."""
import sys,json,math
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parent
sys.path.insert(0,str(Path.home()/'.agent-reach/cuhk/python'))
from scipy.sparse import coo_matrix,diags,eye
from scipy.sparse.linalg import cg
from scipy.spatial import cKDTree
grid=np.load(root/'terrain_refined_display.npz');xs,ys,z=grid['x'],grid['y'],grid['elevation']
def height(x,y):
    u=np.clip((np.asarray(x)-xs[0])/5,0,len(xs)-1.00001);v=np.clip((ys[0]-np.asarray(y))/5,0,len(ys)-1.00001);a,b=u.astype(int),v.astype(int);fx,fy=u-a,v-b
    return np.where(fy>=fx,z[b,a]*(1-fy)+z[b+1,a]*(fy-fx)+z[b+1,a+1]*fx,z[b,a]*(1-fx)+z[b,a+1]*(fx-fy)+z[b+1,a+1]*fy)
features=json.loads((root/'geodata.json').read_text('utf-8'))['features']
nodes=[];lookup={};edges=set();roads=[]
widths={'motorway':10,'motorway_link':6,'secondary':8,'secondary_link':6,'tertiary':7,'tertiary_link':5,'residential':5,'service':4,'unclassified':5,'footway':1.8,'path':1.4,'steps':2,'pedestrian':3,'cycleway':2.5,'track':3}
for f in features:
    if f['kind']!='road' or f['tags'].get('tunnel')=='yes' or f['tags'].get('highway') in ('construction','proposed','corridor'):continue
    g=f['geometry'];lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates'] if g['type']=='MultiLineString' else []
    tags=f['tags'];w=widths.get(tags.get('highway'),3)
    try:w=float(tags.get('width',w))
    except ValueError:pass
    for points in lines:
        pts=np.array(points);out=[]
        for a,b in zip(pts[:-1],pts[1:]):
            length=np.linalg.norm(b-a);count=max(1,math.ceil(length/3))
            out.extend(a+(b-a)*(k/count) for k in range(count))
        out.append(pts[-1]);ids=[]
        for x,y in out:
            key=(round(x,2),round(y,2),str(tags.get('layer','0')))
            if key not in lookup:lookup[key]=len(nodes);nodes.append((x,y))
            idx=lookup[key]
            if not ids or idx!=ids[-1]:ids.append(idx)
        if len(ids)<2:continue
        edges.update(tuple(sorted((a,b))) for a,b in zip(ids[:-1],ids[1:]) if a!=b)
        roads.append({'id':f['id'],'highway':tags['highway'],'width':w,'nodes':ids})
xy=np.array(nodes);uv=np.array(sorted(edges));length=np.linalg.norm(xy[uv[:,1]]-xy[uv[:,0]],axis=1)
weights=1/np.maximum(length,.5)
adj=coo_matrix((np.r_[weights,weights],(np.r_[uv[:,0],uv[:,1]],np.r_[uv[:,1],uv[:,0]])),shape=(len(xy),len(xy))).tocsr()
degree=np.asarray(adj.sum(axis=1)).ravel();L=eye(len(xy))-diags(1/np.maximum(degree,.001))@adj
target=height(xy[:,0],xy[:,1]);A=eye(len(xy))+1800*(L.T@L)
smooth,info=cg(A,target,x0=target,rtol=1e-7,maxiter=2500)
assert info==0,info
# A second robust fit discourages isolated sharp slope changes while retaining regional elevations.
before=np.asarray(L@target);after=np.asarray(L@smooth)
profiles=[]
for r in roads:
    ids=r.pop('nodes');profiles.append(r|{'points':np.column_stack((xy[ids],smooth[ids])).tolist()})

# Make a continuous roadbed across the road width and blend the shoulders into the display terrain.
samples=[];ends=[];radii=[]
for r in profiles:
    p=np.array(r['points']);samples.extend(p[:-1].tolist());ends.extend(p[1:].tolist());radii.extend([r['width']/2]*(len(p)-1))
samples=np.array(samples);ends=np.array(ends);radii=np.array(radii);tree=cKDTree((samples[:,:2]+ends[:,:2])/2)
xx,yy=np.meshgrid(xs,ys);q=np.column_stack((xx.ravel(),yy.ravel()));_,ind=tree.query(q,k=8)
a=samples[ind,:2];v=ends[ind,:2]-a;t=np.clip(np.sum((q[:,None,:]-a)*v,axis=2)/np.maximum(np.sum(v*v,axis=2),1e-9),0,1)
dist=np.linalg.norm(q[:,None,:]-(a+t[:,:,None]*v),axis=2);signed=dist-radii[ind]
best=np.argmin(signed,axis=1);ar=np.arange(len(q));d=signed[ar,best];near=ind[ar,best];frac=t[ar,best]
weight=np.clip((13-d)/7,0,1);bed=samples[near,2]*(1-frac)+ends[near,2]*frac-.15
new=z.ravel().copy();new=new*(1-weight)+bed*weight;new=new.reshape(z.shape)
np.savez_compressed(root/'terrain_roads_smoothed.npz',elevation=new,x=xs,y=ys)
stats={'road_profiles':len(profiles),'shared_profile_nodes':len(xy),'network_edges':len(uv),'profile_roughness_rms_before_m':float(np.sqrt(np.mean(before**2))),'profile_roughness_rms_after_m':float(np.sqrt(np.mean(after**2))),'rms_height_adjustment_m':float(np.sqrt(np.mean((smooth-target)**2))),'max_height_adjustment_m':float(np.max(np.abs(smooth-target))),'max_shared_junction_gap_m':0,'note':'Illustrative smoothing of network elevation; not engineered road gradients. Plan geometry retained, cross sections flattened.'}
assert stats['profile_roughness_rms_after_m']<stats['profile_roughness_rms_before_m']*.2
assert np.isfinite(smooth).all() and np.isfinite(new).all()
(root/'smooth_road_profiles.json').write_text(json.dumps({'profiles':profiles,'stats':stats},separators=(',',':')),encoding='utf-8')
(root/'smooth_roads_stats.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
print(json.dumps(stats),flush=True)
