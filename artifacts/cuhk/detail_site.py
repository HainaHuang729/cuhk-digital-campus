"""Add illustrative site detail to the loaded CUHK scene; does not save or render."""
import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent


def apply_site_details(height_fn=None, road_height_fn=None, junction_clearance=None, sports_surfaces=None, sports_infield_fit=None):
    data = json.loads((ROOT / 'geodata.json').read_text('utf-8'))
    grid = np.load(ROOT / 'terrain.npz')
    xs, ys, raw = grid['x'], grid['y'], grid['elevation']
    pad = np.pad(raw, 1, mode='edge')
    z = sum(pad[j:j+raw.shape[0], i:i+raw.shape[1]] for i in range(3) for j in range(3)) / 9

    def height(x, y):
        u = np.clip((np.asarray(x)-xs[0])/5, 0, len(xs)-1.00001)
        v = np.clip((ys[0]-np.asarray(y))/5, 0, len(ys)-1.00001)
        a, b = u.astype(int), v.astype(int)
        fx, fy = u-a, v-b
        return z[b,a]*(1-fx)*(1-fy)+z[b,a+1]*fx*(1-fy)+z[b+1,a]*(1-fx)*fy+z[b+1,a+1]*fx*fy

    if height_fn is not None:
        height = height_fn
    ground_height = height

    old = bpy.data.collections.get('08 Site details')
    if old:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(old)
    collection = bpy.data.collections.new('08 Site details')
    bpy.context.scene.collection.children.link(collection)
    collection['accuracy'] = 'illustrative; OSM facility geometry and road alignments; fittings and markings are not surveyed'
    palette = {
        'Road paint': (.82, .81, .70), 'Curbs': (.34, .38, .34),
        'Court paint': (.94, .94, .84), 'Pool lane ropes': (.10, .34, .62),
        'Lamp poles': (.11, .16, .16), 'Lamp heads': (.77, .79, .68),
        'Goal frames': (.85, .86, .79), 'Net mesh': (.43, .47, .42),
        'Turf stripes': (.19, .33, .105),
    }
    materials, batches = {}, {}
    for name, color in palette.items():
        mat = bpy.data.materials.get('Detail / '+name) or bpy.data.materials.new('Detail / '+name)
        mat.diffuse_color = (*color, 1)
        mat.use_nodes = True
        mat.node_tree.nodes.clear()
        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
        bsdf.inputs['Base Color'].default_value = (*color, 1)
        bsdf.inputs['Roughness'].default_value = .73
        materials[name] = mat
        batches[name] = [[], []]

    def face(name, points):
        verts, faces = batches[name]
        start = len(verts)
        verts.extend(tuple(float(v) for v in p) for p in points)
        faces.append(tuple(range(start, len(verts))))

    def densify(points, step=2):
        points = np.asarray(points, dtype=float)
        out = []
        for a, b in zip(points[:-1], points[1:]):
            count = max(1, int(math.ceil(np.linalg.norm(b-a)/step)))
            out.extend(a+(b-a)*(i/count) for i in range(count))
        out.append(points[-1])
        return np.asarray(out)

    current_junctions = []

    def drape_line(points, width, elevation, material):
        points = densify(points)
        for a, b in zip(points[:-1], points[1:]):
            vec = b-a
            length = np.linalg.norm(vec)
            if length < .0001 or np.max(np.abs([a, b])) > 1197:
                continue
            if material in ('Curbs','Road paint') and any(np.linalg.norm((a+b)/2-np.asarray(center)) < radius for center,radius in current_junctions):
                continue
            normal = np.array([-vec[1], vec[0]])/length*(width/2)
            xy = np.array([a-normal, b-normal, b+normal, a+normal])
            face(material, np.column_stack((xy, height(xy[:,0], xy[:,1])+elevation)))

    def offset_path(points, distance):
        points = np.asarray(points, dtype=float)
        closed = np.linalg.norm(points[0]-points[-1]) < .001
        p = points[:-1] if closed else points
        d = np.diff(p, axis=0)
        d /= np.maximum(np.linalg.norm(d, axis=1)[:,None], .0001)
        normals = np.column_stack((-d[:,1], d[:,0]))
        result = []
        for i, pt in enumerate(p):
            if closed:
                before = pt-p[i-1]
                after = p[(i+1)%len(p)]-pt
                before /= max(np.linalg.norm(before), .0001)
                after /= max(np.linalg.norm(after), .0001)
                n1, n2 = np.array([-before[1], before[0]]), np.array([-after[1], after[0]])
            else:
                n1, n2 = normals[max(0,i-1)], normals[min(i,len(normals)-1)]
            normal = n1+n2
            normal /= max(np.linalg.norm(normal), .0001)
            result.append(pt + normal*distance/max(.75, float(np.dot(normal,n2))))
        if closed:
            result.append(result[0])
        return np.asarray(result)

    def cylinder(start, end, radius, material, sides=8):
        start, end = Vector(start), Vector(end)
        axis = (end-start).normalized()
        u = axis.cross(Vector((0,0,1)))
        if u.length < .001:
            u = Vector((1,0,0))
        u.normalize()
        v = axis.cross(u)
        ring = [radius*(u*math.cos(i*2*math.pi/sides)+v*math.sin(i*2*math.pi/sides)) for i in range(sides)]
        for i in range(sides):
            j = (i+1)%sides
            face(material, [start+ring[i], start+ring[j], end+ring[j], end+ring[i]])
        face(material, [end+q for q in ring])

    def rectangle_frame(ring):
        points = np.asarray(ring, dtype=float)
        if np.linalg.norm(points[0]-points[-1]) < .001:
            points = points[:-1]
        options = []
        for a, b in zip(points, np.roll(points,-1,axis=0)):
            u = b-a
            if np.linalg.norm(u) < .01:
                continue
            u /= np.linalg.norm(u)
            v = np.array([-u[1],u[0]])
            projected = np.column_stack((points@u, points@v))
            lo, hi = projected.min(axis=0), projected.max(axis=0)
            options.append((float(np.prod(hi-lo)), u.copy(), v, lo, hi))
        if not options:
            return None
        area, u, v, lo, hi = min(options,key=lambda x:x[0])
        poly_area = abs(np.sum(points[:,0]*np.roll(points[:,1],-1)-np.roll(points[:,0],-1)*points[:,1]))/2
        if area < 1 or poly_area/area < .96:
            return None
        length, width = hi-lo
        center = ((lo+hi)/2)[0]*u+((lo+hi)/2)[1]*v
        if width > length:
            length, width, u, v = width, length, v, -u
        return center, u, v, float(length), float(width)

    stats = dict(roads_with_edges=0, roads_with_dashes=0, road_dashes=0, streetlamps=0,
                 soccer_fields=0, basketball_courts=0, tennis_courts=0, running_tracks=0,
                 swimming_pools=0, football_goals=0)
    source_ids = set()
    lamp_positions = []
    obstacles = []
    for item in data['features']:
        if item['kind'] not in ('building','sport','water'):
            continue
        geometry = item['geometry']
        polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else []
        for polygon in polygons:
            ring = np.asarray(polygon[0],dtype=float)
            obstacles.append((ring.min(axis=0),ring.max(axis=0),ring))

    def obstructed(xy):
        for lo,hi,ring in obstacles:
            if not ((xy >= lo).all() and (xy <= hi).all()):
                continue
            inside = False
            x,y = xy
            for a,b in zip(ring[:-1],ring[1:]):
                if (a[1] > y) != (b[1] > y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
                    inside = not inside
            if inside:
                return True
        return False

    for f in data['features']:
        if not f['campus']:
            continue
        height = (lambda x,y,oid=f['id']: road_height_fn(x,y,oid)) if f['kind']=='road' and road_height_fn is not None else ground_height
        current_junctions = (junction_clearance or {}).get(str(f['id']), []) if f['kind']=='road' else []
        tags, geo = f['tags'], f['geometry']
        planar_sport = f['kind']=='sport' and str(f['id']) in (sports_surfaces or {})
        if planar_sport:
            # One facility level also drives its lines, turf and goal frames.
            base = sports_surfaces[str(f['id'])] - (1.3 if tags.get('leisure')=='track' else 1.0)
            height = lambda x,y,base=base: np.full(np.broadcast(np.asarray(x),np.asarray(y)).shape,base)
        if f['kind'] == 'road' and geo['type'] == 'LineString':
            highway = tags.get('highway')
            if highway not in ('secondary','primary','tertiary','residential','unclassified','service') or tags.get('tunnel') == 'yes':
                continue
            if tags.get('service') in ('parking_aisle','driveway'):
                continue
            width = {'primary':9,'secondary':8,'tertiary':7,'residential':5,'service':4,'unclassified':5}[highway]
            try:
                width = float(tags.get('width',width))
            except (TypeError,ValueError):
                pass
            points = densify(geo['coordinates'],2)
            lengths = np.linalg.norm(np.diff(points,axis=0),axis=1)
            distance = np.concatenate(([0],np.cumsum(lengths)))
            if distance[-1] < 20 or width < 4:
                continue
            elevation = .8+.002*(f['id']%101)
            for side in (-1,1):
                drape_line(offset_path(points,side*(width/2-.20)), .18, elevation+.20, 'Curbs')
            stats['roads_with_edges'] += 1
            source_ids.add(f['id'])
            try:
                lanes = int(tags.get('lanes',2 if tags.get('oneway') not in ('yes','-1') else 1))
            except (TypeError,ValueError):
                lanes = 1
            if width >= 5 and lanes >= 2 and tags.get('junction') != 'roundabout':
                # ponytail: schematic central dashed lane division; junction paint awaits surveyed lane geometry.
                for start in np.arange(6,distance[-1]-6,10):
                    end = min(start+4,distance[-1]-6)
                    samples = np.linspace(start,end,max(2,int((end-start)/1.5)+1))
                    xy = np.column_stack((np.interp(samples,distance,points[:,0]),np.interp(samples,distance,points[:,1])))
                    drape_line(xy,.20,elevation+.23,'Road paint')
                    stats['road_dashes'] += 1
                stats['roads_with_dashes'] += 1
            if highway != 'service' and tags.get('name') and distance[-1] > 55:
                for at in np.arange(25,distance[-1]-12,65):
                    idx = min(len(points)-2,int(np.searchsorted(distance,at)))
                    tangent = points[idx+1]-points[idx]
                    tangent /= max(np.linalg.norm(tangent),.001)
                    normal = np.array([-tangent[1],tangent[0]])
                    xy = np.array([np.interp(at,distance,points[:,0]),np.interp(at,distance,points[:,1])])+normal*(width/2+.7)
                    if np.max(np.abs(xy)) > 1195 or any(np.linalg.norm(xy-q)<22 for q in lamp_positions) or obstructed(xy):
                        continue
                    lamp_positions.append(xy)
                    ground = float(height(*xy))+.2
                    top = np.array([*xy,ground+6.5])
                    tip = top-np.array([*normal,0])*1.6
                    cylinder([*xy,ground],top,.115,'Lamp poles')
                    cylinder(top,tip,.075,'Lamp poles')
                    cylinder(tip-np.array([0,0,.12]),tip+np.array([0,0,.12]),.34,'Lamp heads')
                    stats['streetlamps'] += 1
        elif f['kind'] == 'sport':
            sport = tags.get('sport')
            if sport == 'running' and tags.get('leisure') == 'track' and geo['type'] == 'LineString':
                for offset in np.arange(-3.6,3.61,1.2):
                    drape_line(offset_path(geo['coordinates'],offset),.13,1.32 if planar_sport else 1.52,'Court paint')
                stats['running_tracks'] += 1
                source_ids.add(f['id'])
                continue
            if geo['type'] != 'Polygon':
                continue
            frame = rectangle_frame(geo['coordinates'][0])
            if frame is None:
                continue
            center,u,v,length,width = frame
            def world(points):
                pts = np.asarray(points,dtype=float)
                xy = center+pts[:,0,None]*u+pts[:,1,None]*v
                fit = (sports_infield_fit or {}).get(str(f['id']))
                if fit:
                    origin = np.asarray(fit['center_xy'])
                    xy = origin+(xy-origin)*fit['scale']
                return xy
            def line(points,w=.16,offset=1.02 if planar_sport else 1.23,material='Court paint'):
                drape_line(world(points),w,offset,material)
            def box(x1,y1,x2,y2):
                line([(x1,y1),(x2,y1),(x2,y2),(x1,y2),(x1,y1)])
            def circle(x,y,r,count=48):
                line([(x+math.cos(a)*r,y+math.sin(a)*r) for a in np.linspace(0,2*math.pi,count+1)])
            if sport == 'soccer' and length > 55 and width > 35:
                L,W = length-2.0,width-2.0
                # Markings follow mapped field extents; these are deliberately not regulation-size replacements.
                for a in np.arange(-L/2,L/2,10):
                    for x in np.arange(a,min(a+5,L/2),2):
                        for y in np.arange(-W/2,W/2,2):
                            xy=world([(x,y),(min(x+2,L/2),y),(min(x+2,L/2),min(y+2,W/2)),(x,min(y+2,W/2))])
                            face('Turf stripes',np.column_stack((xy,height(xy[:,0],xy[:,1])+(1.01 if planar_sport else 1.07))))
                box(-L/2,-W/2,L/2,W/2)
                line([(0,-W/2),(0,W/2)])
                circle(0,0,min(9.15,W*.19))
                for side in (-1,1):
                    end = side*L/2
                    box(end,-min(20.16,W*.40),end-side*min(16.5,L*.19),min(20.16,W*.40))
                    box(end,-9.16,end-side*5.5,9.16)
                    goalxy = world([(end,-3.66),(end,3.66)])
                    goalzz = height(goalxy[:,0],goalxy[:,1])+(1.0 if planar_sport else 1.15)
                    left,right = [np.array([*q,h]) for q,h in zip(goalxy,goalzz)]
                    up = np.array([0,0,2.44])
                    cylinder(left,left+up,.10,'Goal frames')
                    cylinder(right,right+up,.10,'Goal frames')
                    cylinder(left+up,right+up,.10,'Goal frames')
                    for y in np.linspace(-3.66,3.66,13):
                        q=world([(end,y)])[0]
                        goalz=float(np.interp(y,[-3.66,3.66],goalzz))
                        cylinder([*q,goalz],[*q,goalz+2.44],.018,'Net mesh',4)
                    stats['football_goals'] += 1
                stats['soccer_fields'] += 1
            elif sport == 'basketball' and length >= 25 and width >= 13:
                L,W = min(28,length-.7),min(15,width-.7)
                box(-L/2,-W/2,L/2,W/2)
                line([(0,-W/2),(0,W/2)])
                circle(0,0,1.8)
                for side in (-1,1):
                    box(side*L/2,-2.45,side*(L/2-5.8),2.45)
                    circle(side*(L/2-5.8),0,1.8)
                    # Schematic free-throw circles and keys; mapped court orientation is retained.
                stats['basketball_courts'] += 1
            elif sport == 'tennis' and length >= 22 and width >= 10:
                L,W = min(23.77,length-.5),min(10.97,width-.5)
                box(-L/2,-W/2,L/2,W/2)
                for side in (-1,1):
                    line([(-L/2,side*min(4.115,W*.375)),(L/2,side*min(4.115,W*.375))])
                    line([(side*6.4,-min(4.115,W*.375)),(side*6.4,min(4.115,W*.375))])
                line([(-6.4,0),(6.4,0)])
                net = world([(0,-W/2-.35),(0,W/2+.35)])
                zz = height(net[:,0],net[:,1])+2.08
                cylinder([*net[0],zz[0]],[*net[1],zz[1]],.035,'Net mesh')
                for q,h in zip(net,zz):
                    cylinder([*q,h-.97],[*q,h+.1],.07,'Lamp poles')
                stats['tennis_courts'] += 1
            elif tags.get('leisure') == 'swimming_pool' and length >= 20 and width >= 8 and tags.get('level','0') == '0':
                lanes = max(3,int(width/2.5))
                for across in np.linspace(-width/2+.4,width/2-.4,lanes+1):
                    line([(-length/2+.4,across),(length/2-.4,across)],.13,1.73,'Pool lane ropes')
                stats['swimming_pools'] += 1
            else:
                continue
            source_ids.add(f['id'])

    for name,(verts,faces) in batches.items():
        if not faces:
            continue
        mesh=bpy.data.meshes.new('Site / '+name)
        mesh.from_pydata(verts,[],faces)
        mesh.update()
        obj=bpy.data.objects.new('Site / '+name,mesh)
        collection.objects.link(obj)
        mesh.materials.append(materials[name])
        obj['detail_type']='illustrative'
        obj['placement_source']='Existing OSM local-metre geometries, matched to smoothed source DTM'
    collection['source_osm_ids']=json.dumps(sorted(source_ids))
    stats['objects']=len(collection.objects)
    stats['vertices']=sum(len(o.data.vertices) for o in collection.objects)
    assert stats['soccer_fields']==3 and stats['running_tracks']==2 and stats['swimming_pools']==1,stats
    assert all(np.isfinite(v.co).all() for o in collection.objects for v in o.data.vertices)
    print('SITE_DETAIL_STATS',json.dumps(stats),flush=True)
    return stats


if __name__=='__main__':
    apply_site_details()
