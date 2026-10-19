"""Read-only audit of actual road/terrain meshes; run with Blender --background --python.

Usage: -- --source CUHK_roads_graded.blend [--network road_network_v3.json]
       -- --self-test
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import time

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent


def world_vertices(obj, mesh):
    co = np.empty(len(mesh.vertices)*3, dtype=np.float32)
    mesh.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    matrix = np.asarray(obj.matrix_world, dtype=np.float32)
    return co @ matrix[:3, :3].T + matrix[:3, 3]


def triangles(mesh):
    counts = np.empty(len(mesh.polygons), dtype=np.int32)
    mesh.polygons.foreach_get('loop_total', counts)
    if np.all(counts == 3):
        ix = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get('vertex_index', ix)
        return ix.reshape(-1, 3)
    mesh.calc_loop_triangles()
    ix = np.empty(len(mesh.loop_triangles)*3, dtype=np.int32)
    mesh.loop_triangles.foreach_get('vertices', ix)
    return ix.reshape(-1, 3)


class TerrainGrid:
    """Use real mesh Z and real per-cell triangle diagonals, not the NPZ height values."""
    def __init__(self, xyz, tris, shape):
        self.ny, self.nx = shape
        assert len(xyz) == self.nx*self.ny, 'Terrain mesh vertex count disagrees with display_grid_path'
        co = xyz.reshape(self.ny, self.nx, 3)
        self.x = co[0, :, 0].astype(float)
        self.y = co[:, 0, 1].astype(float)
        self.z = co[:, :, 2]
        assert np.all(np.diff(self.x)>0) and np.all(np.diff(self.y)<0), 'Expected increasing X / decreasing Y regular mesh indexing'
        assert np.max(abs(co[:, :, 0]-self.x)) < .002 and np.max(abs(co[:, :, 1]-self.y[:, None])) < .002, 'Actual terrain is not an axis-aligned height field'
        assert np.isfinite(xyz).all(), 'Nonfinite terrain vertices'
        total_cells = (self.nx-1)*(self.ny-1)
        diag = np.full(total_cells, -1, dtype=np.int8)
        hits = np.zeros(total_cells, dtype=np.uint8)
        # Chunk validation avoids allocating multiple full-size triangle-coordinate arrays.
        for start in range(0, len(tris), 200000):
            t = tris[start:start+200000]
            rr, cc = t//self.nx, t%self.nx
            r, c = rr.min(axis=1), cc.min(axis=1)
            assert np.all(rr.max(axis=1)-r == 1) and np.all(cc.max(axis=1)-c == 1), 'Terrain contains triangles spanning multiple grid cells'
            corners = (rr-r[:, None])*2 + cc-c[:, None]
            main = np.any(corners==0, axis=1) & np.any(corners==3, axis=1)
            other = np.any(corners==1, axis=1) & np.any(corners==2, axis=1)
            assert np.all(main ^ other), 'Invalid terrain grid triangle'
            ids = r*(self.nx-1)+c
            proposed = main.astype(np.int8)
            prior = diag[ids]
            assert np.all((prior<0) | (prior==proposed)), 'Inconsistent diagonals in terrain cell'
            # Also catch two inconsistent triangles within this same chunk.
            order = np.argsort(ids)
            assert not np.any((np.diff(ids[order])==0) & (np.diff(proposed[order])!=0)), 'Crossed terrain triangulation'
            diag[ids] = proposed
            np.add.at(hits, ids, 1)
        assert np.all(hits==2), 'Terrain grid has missing/duplicated triangles'
        self.diag = diag.reshape(self.ny-1, self.nx-1)
        self.info = {'rows':self.ny, 'columns':self.nx, 'x_spacing_m': [float(np.diff(self.x).min()),float(np.diff(self.x).max())],
                     'y_spacing_m':[float((-np.diff(self.y)).min()),float((-np.diff(self.y)).max())],
                     'triangles':len(tris), 'diagonal_main_cells':int((diag==1).sum()),
                     'diagonal_other_cells':int((diag==0).sum()), 'actual_mesh_topology_verified':True}

    def height(self, x, y):
        x, y = np.asarray(x), np.asarray(y)
        inside = (x>=self.x[0]) & (x<=self.x[-1]) & (y<=self.y[0]) & (y>=self.y[-1])
        c = np.clip(np.searchsorted(self.x, x, side='right')-1, 0, self.nx-2)
        r = np.clip(np.searchsorted(-self.y, -y, side='right')-1, 0, self.ny-2)
        fx, fy = (x-self.x[c])/(self.x[c+1]-self.x[c]), (self.y[r]-y)/(self.y[r]-self.y[r+1])
        a,b,corn,d = self.z[r,c],self.z[r,c+1],self.z[r+1,c],self.z[r+1,c+1]
        main = np.where(fy>=fx, a*(1-fy)+corn*(fy-fx)+d*fx, a*(1-fx)+b*(fx-fy)+d*fy)
        other = np.where(fx+fy<=1, a*(1-fx-fy)+b*fx+corn*fy, b*(1-fy)+corn*(1-fx)+d*(fx+fy-1))
        return np.where(inside, np.where(self.diag[r,c], main, other), np.nan)


def visible_for_render(scene):
    found = set()
    def walk(lc):
        if lc.exclude or lc.collection.hide_render:
            return
        found.update(o.name for o in lc.collection.objects if not o.hide_render)
        for child in lc.children:
            walk(child)
    for view in scene.view_layers:
        if view.use:
            walk(view.layer_collection)
    return found


def resolve(value, source):
    path = Path(str(value))
    if str(value).startswith('//'):
        return Path(bpy.path.abspath(str(value)))
    if path.is_absolute():
        return path
    a = source.parent/path
    return a if a.exists() else ROOT/path


def surface_class(obj, features):
    explicit = str(obj.get('surface_class', ''))
    if explicit:
        return 'ground' if explicit in ('junction','ground_junction') else explicit
    tags = features.get(str(obj.get('osm_id')), {}).get('tags', {})
    if tags.get('tunnel', 'no') not in ('no',''):
        return 'tunnel'
    if tags.get('indoor')=='yes' or tags.get('highway')=='corridor':
        return 'indoor'
    layer = float(tags.get('layer', 0))
    if tags.get('bridge','no') not in ('no','') or layer>0:
        return 'elevated'
    return 'below_ground' if layer<0 else 'ground'


def flip_candidates(tris, xyz):
    """Opposite projected orientation across a shared edge flags an actual fold/winding issue."""
    p = xyz[tris]
    nz = np.cross(p[:,1]-p[:,0], p[:,2]-p[:,0])[:,2]
    edges = np.concatenate((tris[:,[0,1]],tris[:,[1,2]],tris[:,[2,0]]))
    sign = np.tile(np.sign(nz), 3)
    face = np.tile(np.arange(len(tris)), 3)
    edges.sort(axis=1)
    order = np.lexsort((edges[:,1],edges[:,0]))
    same = np.all(edges[order[1:]]==edges[order[:-1]],axis=1)
    at = np.where(same & (sign[order[1:]]*sign[order[:-1]]<0))[0]
    examples=[]
    for k in at[:12]:
        edge=edges[order[k]]
        examples.append({'edge_vertex_ids':edge.tolist(),'point':xyz[edge].mean(axis=0).tolist(),
                         'triangles':[int(face[order[k]]),int(face[order[k+1]])]})
    return {'opposite_projected_winding_shared_edges':len(at),'examples':examples,
            'note':'Candidate fold or inconsistent triangle winding. This alone cannot distinguish intentional overlapping ribbons from malformed lateral geometry.'}


def audit_mesh(obj, xyz, tris, terrain, gap, threshold):
    p = xyz[tris].astype(float)
    cross = np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
    projected = abs(cross[:,2])*.5
    keep = projected>1e-8
    has_solidify = any(m.type=='SOLIDIFY' and m.show_render for m in obj.modifiers)
    if has_solidify:
        keep &= cross[:,2]>0  # Bottom slab faces intentionally do not represent pavement tops.
    p, projected = p[keep],projected[keep]
    if not len(p):
        return None,p
    maxedge = np.maximum.reduce([np.linalg.norm(p[:,i,:2]-p[:,j,:2],axis=1) for i,j in [(0,1),(1,2),(2,0)]])
    divisions = np.maximum(2,np.ceil(maxedge/gap).astype(int))
    assert divisions.max()<=250, f'Road triangle requires >250 subdivisions: {obj.name}; inspect unusually huge geometry'
    minclear = np.full(len(p),np.inf)
    badcounts = np.zeros(len(p),np.int32)
    validcounts = np.zeros(len(p),np.int32)
    outside=0;total=0;worst=None;minimum=np.inf
    for n in np.unique(divisions):
        ids = np.flatnonzero(divisions==n)
        weights = np.array([(i/n,j/n,1-(i+j)/n) for i in range(n+1) for j in range(n+1-i)]
                           + ([(.5,.5,0),(.5,0,.5),(0,.5,.5)] if n%2 else []) + [(1/3,1/3,1/3)])
        for start in range(0,len(ids),max(1,200000//len(weights))):
            batch=ids[start:start+max(1,200000//len(weights))]
            probes=np.einsum('wv,tvd->twd',weights,p[batch])
            heights=terrain.height(probes[:,:,0],probes[:,:,1])
            clearance=probes[:,:,2]-heights
            valid=np.isfinite(clearance)
            bad=valid & (clearance<=threshold)
            safe=np.where(valid,clearance,np.inf)
            local=safe.min(axis=1)
            minclear[batch]=local;badcounts[batch]=bad.sum(axis=1);validcounts[batch]=valid.sum(axis=1)
            outside+=int((~valid).sum());total+=int(valid.size)
            if local.min()<minimum:
                pos=np.unravel_index(np.argmin(safe),safe.shape)
                minimum=float(safe[pos]);worst=probes[pos].tolist()
    return {'object':obj.name,'osm_id':str(obj.get('osm_id','')),'profile_index':obj.get('profile_index'),
            'part':obj.get('part',obj.get('profile_part',0)), 'triangles':len(p),'probe_count':total,
            'in_terrain_probe_count':int(validcounts.sum()),'outside_terrain_probes':outside,
            'buried_probes':int(badcounts.sum()),'min_clearance_m':None if not np.isfinite(minimum) else minimum,
            'buried_area_estimate_m2':float((projected*badcounts/np.maximum(validcounts,1)).sum()),
            'projected_area_m2':float(projected.sum()),'worst_point':worst,'max_triangle_edge_m':float(maxedge.max()),
            'solidify_bottom_faces_excluded':has_solidify,'fold_check':flip_candidates(tris[keep],xyz)},p


def mesh_height_at(triangles_xyz, xy, reference):
    p=triangles_xyz
    if not len(p):
        return None
    # Exact projected triangle coverage at a shared source node, with small float tolerance.
    mask=np.all(np.asarray(xy)>=p[:,:,:2].min(axis=1)-.001,axis=1)&np.all(np.asarray(xy)<=p[:,:,:2].max(axis=1)+.001,axis=1)
    q=p[mask]
    if not len(q):
        return None
    a=q[:,0,:2];v=q[:,1,:2]-a;w=q[:,2,:2]-a;d=np.asarray(xy)-a
    det=v[:,0]*w[:,1]-v[:,1]*w[:,0]
    u=(d[:,0]*w[:,1]-d[:,1]*w[:,0])/det
    t=(v[:,0]*d[:,1]-v[:,1]*d[:,0])/det
    inside=(u>=-1e-4)&(t>=-1e-4)&(u+t<=1.0001)
    h=(q[:,0,2]+u*(q[:,1,2]-q[:,0,2])+t*(q[:,2,2]-q[:,0,2]))[inside]
    return None if not len(h) else float(h[np.argmin(abs(h-reference))])


def junction_audit(network, mesh_entries):
    by_index=defaultdict(list);by_id=defaultdict(list)
    for row,p in mesh_entries:
        if row['profile_index'] is not None:
            by_index[int(row['profile_index'])].append((row,p))
        by_id[(row['osm_id'],int(row['part']))].append((row,p))
    checked=[];incomplete=[];skipped=0
    for junction in network.get('junctions',[]):
        point=junction.get('xyz',junction.get('point'))
        if point is None:
            incomplete.append({'node_index':junction.get('node_index'),'reason':'missing_xyz'});continue
        incident=junction.get('incident_roads',[])
        results=[]
        for road in incident:
            if road.get('surface_class') not in ('ground','elevated'):
                continue
            candidates=by_index.get(road.get('profile_index'),[]) or by_id.get((str(road['id']),int(road.get('part',0))),[])
            if not candidates:
                # Hidden/non-rendered profiles are outside the visible-road acceptance target.
                continue
            heights=[]
            for row,p in candidates:
                h=mesh_height_at(p,point[:2],float(point[2])+.15)
                if h is not None:
                    heights.append(h)
            results.append({'id':road['id'],'profile_index':road.get('profile_index'),
                            'height_m':None if not heights else min(heights,key=lambda h:abs(h-point[2]-.15))})
        if len(results)<2:
            skipped+=1;continue
        missing=[r for r in results if r['height_m'] is None]
        if missing:
            incomplete.append({'node_index':junction.get('node_index'),'xy':point[:2],'reason':'incident_mesh_does_not_cover_shared_center','incident':results})
            continue
        heights=[r['height_m'] for r in results]
        checked.append({'node_index':junction.get('node_index'),'osm_node_id':junction.get('osm_node_id'),
                        'xy':point[:2],'height_gap_m':max(heights)-min(heights),'incident':results})
    return {'checked_shared_nodes':len(checked),'skipped_fewer_than_two_visible_incident_roads':skipped,
            'nodes_with_height_gap_above_0_05m':sum(r['height_gap_m']>.05 for r in checked),
            'max_height_gap_m':max((r['height_gap_m'] for r in checked),default=None),
            'missing_center_coverage_or_mapping':len(incomplete),'incomplete_examples':incomplete[:40],
            'worst':sorted(checked,key=lambda r:r['height_gap_m'],reverse=True)[:25],
            'note':'Tests actual individual incident mesh coverage/heights at shared source nodes. Intentionally trimmed branches filled by a separate junction patch require review of missing-center examples.'}


def self_test():
    xyz=np.array([[0,0,0],[2,0,0],[4,0,0],[0,-3,0],[2,-3,10],[4,-3,0]],float)
    tri=np.array([[0,3,4],[0,4,1],[1,4,2],[2,4,5]])
    g=TerrainGrid(xyz,tri,(2,3))
    assert np.allclose(g.height([.5,2.5],[-2.25,-2.25]),[2.5,7.5])
    assert np.isnan(g.height(np.array([-1]),np.array([-1]))).all()
    p=np.array([[[0,0,1],[1,0,1],[0,1,1]]],float)
    assert abs(mesh_height_at(p,[.25,.25],1)-1)<1e-10
    assert mesh_height_at(p,[2,2],1) is None
    flat=xyz.copy();flat[:,2]=0
    flat_grid=TerrainGrid(flat,tri,(2,3))
    obj=bpy.data.objects.new('Audit self-test temporary object',None)
    try:
        coords=np.array([[0,0,-.1],[1,0,-.1],[0,-1,-.1]],float)
        row,_=audit_mesh(obj,coords,np.array([[0,1,2]]),flat_grid,1,-.05)
        assert row['buried_probes']==row['probe_count'] and abs(row['min_clearance_m']+.1)<1e-10
        coords[:,2]=.1
        row,_=audit_mesh(obj,coords,np.array([[0,1,2]]),flat_grid,1,-.05)
        assert row['buried_probes']==0 and abs(row['min_clearance_m']-.1)<1e-10
        folded=np.array([[0,0,0],[1,0,0],[0,-1,0],[1,-1,0]],float)
        assert flip_candidates(np.array([[0,1,2],[1,2,3]]),folded)['opposite_projected_winding_shared_edges']==1
    finally:
        bpy.data.objects.remove(obj)
    print('AUDIT_V3_SELF_TEST_PASSED: 2m/3m grid, both diagonals, real mesh Z, bounds, node coverage, buried/clear surfaces, winding inversion',flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('blend',nargs='?');parser.add_argument('--source');parser.add_argument('--network')
    parser.add_argument('--output',default='road_surface_v3_audit.json');parser.add_argument('--max-probe-spacing',type=float,default=1.0)
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if args.self_test:
        self_test();return
    source=Path(args.source or args.blend or ROOT/'CUHK_roads_graded.blend').resolve()
    if not source.exists():
        source=ROOT/(args.source or args.blend or 'CUHK_roads_graded.blend')
    out=Path(args.output)
    if not out.is_absolute():out=ROOT/out
    started=time.time();result={'source':str(source),'status':'incomplete'}
    try:
        bpy.ops.wm.open_mainfile(filepath=str(source))
        scene=bpy.context.scene;visible=visible_for_render(scene)
        terrain_obj=next(o for o in scene.objects if o.name in visible and o.type=='MESH' and 'display_grid_path' in o)
        grid_path=resolve(terrain_obj['display_grid_path'],source)
        with np.load(grid_path) as grid:
            shape=(len(grid['y']),len(grid['x']))
        depsgraph=bpy.context.evaluated_depsgraph_get()
        evaluated=terrain_obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
        terrain=TerrainGrid(world_vertices(evaluated,mesh),triangles(mesh),shape)
        evaluated.to_mesh_clear()
        result['terrain']={**terrain.info,'object':terrain_obj.name,'display_grid_path':str(grid_path)}
        print('AUDIT_V3_TERRAIN',json.dumps(result['terrain']),flush=True)
        features={str(f['id']):f for f in json.loads((ROOT/'geodata.json').read_text(encoding='utf-8'))['features'] if f['kind']=='road'}
        collections=[c for c in bpy.data.collections if c.name.startswith('04') and ('Road' in c.name or 'road' in c.name)]
        road_names={o.name for c in collections for o in c.all_objects}
        road_names.update(o.name for o in scene.objects if str(o.get('osm_id')) in features and 'surface_class' in o)
        rows=[];entries=[];exclusions=Counter();modifier_mismatch=[]
        gap=min(args.max_probe_spacing,float(np.diff(terrain.x).min()),float((-np.diff(terrain.y)).min()))
        assert gap>0
        for obj in [terrain_obj]+[o for o in scene.objects if o.name in road_names and o.name in visible]:
            for m in obj.modifiers:
                if m.show_render != m.show_viewport:
                    modifier_mismatch.append({'object':obj.name,'modifier':m.name,'show_render':m.show_render,'show_viewport':m.show_viewport})
        for obj in scene.objects:
            if obj.name not in road_names or obj.type!='MESH':continue
            if obj.name not in visible:
                exclusions['hidden_for_render']+=1;continue
            klass=surface_class(obj,features)
            if klass not in ('ground','elevated'):
                exclusions[klass]+=1;continue
            evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
            row,p=audit_mesh(obj,world_vertices(evaluated,mesh),triangles(mesh),terrain,gap,-.05)
            evaluated.to_mesh_clear()
            if row is None:
                exclusions['no_projected_surface_triangles']+=1;continue
            row['surface_class']=klass;rows.append(row);entries.append((row,p))
            if len(rows)%200==0:print('AUDIT_V3_ROADS',len(rows),flush=True)
        network_value=args.network or scene.get('road_network_path')
        if network_value is None:
            network_value=next((c.get('road_network_path') for c in collections if c.get('road_network_path')),None)
        network_value=network_value or 'road_network_v2.json'
        network_path=resolve(network_value,source)
        network=json.loads(network_path.read_text(encoding='utf-8'))
        junctions=junction_audit(network,entries)
        result.update({'status':'complete','method':'Actual evaluated mesh triangles; road vertices, edge/interior barycentric lattice and centroids vs verified terrain triangle diagonals. Approximate sampling audit, not exact mesh Boolean intersection.',
                       'burial_threshold_m':-.05,'maximum_probe_spacing_m':gap,'roads':len(rows),'surface_class_counts':dict(Counter(r['surface_class'] for r in rows)),
                       'roads_with_buried_samples':sum(r['buried_probes']>0 for r in rows),'buried_probe_count':sum(r['buried_probes'] for r in rows),
                       'total_probes':sum(r['probe_count'] for r in rows),'outside_terrain_probes':sum(r['outside_terrain_probes'] for r in rows),
                       'min_clearance_m':min((r['min_clearance_m'] for r in rows if r['min_clearance_m'] is not None),default=None),
                       'estimated_buried_area_m2':sum(r['buried_area_estimate_m2'] for r in rows),
                       'render_modifier_mismatch':modifier_mismatch,'excluded_objects':dict(exclusions),'network_path':str(network_path),
                       'shared_node_mesh_continuity':junctions,'roads_with_fold_candidates':sum(r['fold_check']['opposite_projected_winding_shared_edges']>0 for r in rows),
                       'worst':sorted(rows,key=lambda r:r['buried_area_estimate_m2'],reverse=True)[:35],'all':rows})
        result['sampled_no_burial_pass']=bool(rows) and result['buried_probe_count']==0 and not modifier_mismatch
        result['shared_node_height_pass']=junctions['checked_shared_nodes']>0 and junctions['nodes_with_height_gap_above_0_05m']==0 and junctions['missing_center_coverage_or_mapping']==0
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        result['elapsed_seconds']=time.time()-started
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('AUDIT_V3_RESULT',json.dumps({k:v for k,v in result.items() if k not in ('all','worst','shared_node_mesh_continuity')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
