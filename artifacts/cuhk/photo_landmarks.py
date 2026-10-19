"""Six photo-referenced exterior approximations; no surveyed facade dimensions.

Call apply_landmarks(collection, {str(osm_id): source_object}) in Blender.
Sources remain intact but hidden; output geometry is merged per landmark.
Evidence: ~/.agent-reach/cuhk/landmarks/landmarks.json.
"""
import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from detail_buildings import _material


def apply_landmarks(group, sources):
    evidence = json.loads((Path.home()/'.agent-reach/cuhk/landmarks/landmarks.json').read_text('utf-8'))
    references = {r['osm_id']: r for r in evidence['buildings']}
    grid = np.load(Path(__file__).resolve().parent/'terrain_roads_smoothed.npz')
    xs, ys, terrain = grid['x'], grid['y'], grid['elevation']

    def ground(x,y):
        u = min(max((x-float(xs[0]))/float(xs[1]-xs[0]),0),len(xs)-1.00001)
        v = min(max((float(ys[0])-y)/float(ys[0]-ys[1]),0),len(ys)-1.00001)
        a,b = int(u),int(v)
        fx,fy = u-a,v-b
        # Match the existing terrain mesh diagonal, as label_and_smooth.py does.
        if fy>=fx:
            return float(terrain[b,a]*(1-fy)+terrain[b+1,a]*(fy-fx)+terrain[b+1,a+1]*fx)
        return float(terrain[b,a]*(1-fx)+terrain[b,a+1]*(fx-fy)+terrain[b+1,a+1]*fy)
    ids = ('134410449', '107139030', '134410450', '201907977', '201907981', '1424900701')
    mats = [
        _material('Photo landmarks / warm white concrete', (.80, .82, .78), .78),
        _material('Photo landmarks / grey concrete', (.52, .54, .50), .85),
        _material('Photo landmarks / warm formlined concrete', (.50, .48, .42), .86),
        _material('Photo landmarks / recessed blue grey glass', (.06, .14, .18), .24, .32),
        _material('Photo landmarks / dark steel', (.075, .085, .082), .43, .5),
        _material('Photo landmarks / white sunshade', (.88, .89, .85), .65),
        _material('Photo landmarks / roof membrane', (.27, .29, .28), .9),
        _material('Photo landmarks / crest purple proxy', (.20, .047, .24), .6),
        _material('Photo landmarks / crest gold proxy', (.62, .43, .10), .45, .25),
    ]
    stats = {'photo_landmarks': 0, 'objects': [], 'vertices': 0, 'faces': 0,
             'accuracy': 'Photograph-guided approximate exterior geometry; dimensions not surveyed.'}
    for osm_id in ids:
        src = sources.get(osm_id)
        if src is None:
            continue
        # Only replace this building's generated geometry in the supplied collection.
        for ob in list(group.objects):
            if str(ob.get('osm_id', '')) == osm_id:
                mesh = ob.data
                bpy.data.objects.remove(ob, do_unlink=True)
                if isinstance(mesh, bpy.types.Mesh) and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
        points = [src.matrix_world @ v.co for v in src.data.vertices]
        low, high = min(p.z for p in points), max(p.z for p in points)
        H = high-low
        if osm_id == '134410449':
            U = Vector((0, 1, 0))  # Front faces east along the University Mall.
            H = max(H, 19.)
        elif osm_id == '134410450':
            U = Vector((0, -1, 0))  # Auditorium faces west along the same mall.
            H = max(H, 12.)
        elif osm_id in ('201907977', '201907981'):
            # Only side-wall base edges establish orientation; roof triangulation
            # diagonals can be longer than the footprint's actual principal edge.
            edges = []
            for p in src.data.polygons:
                if abs(p.normal.z) > .02 or len(p.vertices) != 4:
                    continue
                a,b = sorted((points[i] for i in p.vertices),key=lambda q:q.z)[:2]
                delta = b-a
                delta.z = 0
                if delta.length > .01:
                    edges.append(delta)
            if not edges:
                raise ValueError('No source footprint walls for landmark '+osm_id)
            U = max(edges, key=lambda v: v.length).normalized()
            if U.x < 0:
                U = -U
        else:
            U = Vector((1, 0, 0))
        if osm_id == '107139030':
            H = max(H, 13.)
        if osm_id == '1424900701':
            H = max(H, 18.)
        V = Vector((-U.y, U.x, 0))
        ux = [p.dot(U) for p in points]
        vy = [p.dot(V) for p in points]
        W, D = max(ux)-min(ux), max(vy)-min(vy)
        center = U*((min(ux)+max(ux))/2)+V*((min(vy)+max(vy))/2)+Vector((0, 0, low))
        verts, faces, mi = [], [], []
        ground_samples, extended_bases = [], []

        def world(p):
            q=center+U*p[0]+V*p[1]+Vector((0, 0, p[2]))
            if p[2] <= .0001:
                surface=ground(q.x,q.y)
                ground_samples.append(surface)
                original_z=q.z
                q.z=min(q.z,surface-.2)
                if q.z<original_z-.001:
                    extended_bases.append(original_z-q.z)
            return tuple(q)

        def poly(coords, material):
            first = len(verts)
            verts.extend(world(p) for p in coords)
            faces.append(tuple(range(first, len(verts))))
            mi.append(material)

        def box(x, y, z, w, d, h, material=0):
            assert min(w, d, h) > 0, (osm_id, w, d, h)
            corners = [(x+sx*w/2, y+sy*d/2, z+sz*h/2)
                       for sz in (-1, 1) for sx, sy in ((-1,-1),(1,-1),(1,1),(-1,1))]
            start = len(verts)
            verts.extend(world(p) for p in corners)
            for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
                faces.append(tuple(start+i for i in f)); mi.append(material)

        def prism(coords, z0, z1, material=0):
            poly([(x,y,z0) for x,y in reversed(coords)], material)
            poly([(x,y,z1) for x,y in coords], material)
            for a,b in zip(coords, coords[1:]+coords[:1]):
                poly([(*a,z0),(*b,z0),(*b,z1),(*a,z1)], material)

        def beam(a, b, width, depth, material=0):
            a,b = Vector(a), Vector(b)
            tangent = (b-a).normalized()
            side = tangent.cross(Vector((0,1,0)))
            if side.length < .01:
                side = tangent.cross(Vector((1,0,0)))
            side.normalize()
            other = tangent.cross(side).normalized()
            cs = [tuple(end+side*s*width/2+other*t*depth/2)
                  for end in (a,b) for s,t in ((-1,-1),(1,-1),(1,1),(-1,1))]
            for end_index,end in enumerate((a,b)):
                if end.z<=.0001:
                    for i in range(end_index*4,end_index*4+4):
                        cs[i]=(cs[i][0],cs[i][1],0.)
            for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
                poly([cs[i] for i in f], material)

        def facade(y, length, z0, height, bays, rows, slit=False, material=0):
            for row in range(rows):
                for bay in range(bays):
                    x = (bay+.5)*length/bays-length/2
                    box(x, y, z0+(row+.5)*height/rows,
                        length/bays*(.22 if slit else .74), .09,
                        height/rows*(.76 if slit else .66), 3)
                if not slit and rows > 1:
                    box(0, y-.19, z0+(row+1)*height/rows-.12,
                        length+.2, .45, .22, material)

        if osm_id == '134410449':
            # Original library only: the adjacent glazed extension has its own footprint.
            box(0, D*.035, H*.255, W*.91, D*.87, H*.51)
            box(0, 0, H*.745, W, D, H*.49)
            box(0, -D*.456, H*.47, W*.99, .35, H*.12)
            box(0, 0, H+.06, W*.97, D*.97, .12, 6)
            for side in (-1,1):
                y = side*(D/2+.06)
                facade(y, W*.94, H*.55, H*.43, 20, 2, True)
                for n in range(21):
                    box((n/20-.5)*W*.96, y, H*.755, .18, .34, H*.49, 5)
                facade(side*D*.47, W*.85, .8, H*.35, 8, 1, True)
            # Thin portico, two posts and dark glazing in recess.
            box(0, -D*.44-.02, H*.105, W*.31, .12, H*.21, 3)
            canopy=sources.get('1072300300')
            if canopy is not None:
                # The mapped entrance is building=roof, not a one-storey room.
                # Replace its old solid extrusion with a thin roof on posts.
                canopy.hide_render=True
                canopy.hide_set(True)
                canopy['photo_replaced_by']=osm_id
                cp=[canopy.matrix_world@v.co-center for v in canopy.data.vertices]
                cx=[p.dot(U) for p in cp];cy=[p.dot(V) for p in cp]
                porch_x=(min(cx)+max(cx))/2
                porch_front=min(cy)
                porch_back=-D*.435
                porch_w=max(cx)-min(cx)
            else:
                porch_x,porch_front,porch_back,porch_w=0,-D*.68,-D*.435,W*.25
            box(porch_x,(porch_front+porch_back)/2,H*.24,
                porch_w,porch_back-porch_front,.20,5)
            for x in (porch_x-porch_w*.46,porch_x+porch_w*.46):
                box(x,porch_front+.23,H*.12,.24,.24,H*.24,5)

        elif osm_id == '107139030':
            box(0, D*.035, H*.43, W*.96, D*.91, H*.86)
            box(0, D*.17, H*.87, W*.76, D*.53, H*.26)
            box(0, D*.17, H+.04, W*.72, D*.48, .15, 6)
            box(0, -D*.459, H*.58, W*.96, .3, H*.26, 1)
            for n in range(95):
                box((n/94-.5)*W*.94, -D*.47, H*.58, .085, .13, H*.26, 0)
            # Opaque theatre fascia and underhung ribs, not an office window grid.
            box(W*.09, -D*.30, H*.88, W*.78, D*.33, H*.20)
            for n in range(5):
                box((n/4-.5)*W*.65+W*.08, -D*.26, H*.71, .85, D*.40, .8)
            box(-W*.29, -D*.462, H*.17, W*.25, .13, H*.30, 3)
            box(-W*.29, -D*.49, H*.335, W*.28, D*.15, .25, 5)
            for n in range(4):
                box(-W*.29, -D*.49-n*.27, .14+n*.14, W*.3, .34, .25, 1)

        elif osm_id == '134410450':
            # A faceted ring and exposed supporting core give the rice-cooker silhouette.
            outer=[(W*.48*math.cos(a), D*.47*math.sin(a))
                   for a in [2*math.pi*n/16 for n in range(16)]]
            core=[(W*.17*math.cos(a), D*.17*math.sin(a))
                  for a in [2*math.pi*n/16 for n in range(16)]]
            prism(core, 0, H*.48, 1)
            prism(outer, H*.44, H*.56, 0)
            prism([(x*.82,y*.82) for x,y in outer], H*.56, H*.87, 1)
            prism(outer, H*.86, H, 0)
            for n in range(12):
                a=2*math.pi*n/12
                x,y=W*.475*math.cos(a),D*.475*math.sin(a)
                box(x,y,H*.72,.57,.60,H*.61,0)
                beam((x*.35,y*.35,H*.31),(x,y,H*.49),.6,.8,0)
            # Simplified purple/gold identification plaque; not a recreated official crest.
            box(0,-D*.474,H*.82,W*.24,.20,H*.34,0)
            shield=[(-W*.062,-D*.488,H*.91),(W*.062,-D*.488,H*.91),
                    (W*.055,-D*.488,H*.77),(0,-D*.488,H*.715),(-W*.055,-D*.488,H*.77)]
            poly(shield,8)
            poly([(x*.76,y-.01,H*.815+(z-H*.815)*.78) for x,y,z in shield],7)

        elif osm_id == '201907977':
            # Seven mapped levels form grouped volumes and a lofty open podium.
            box(0,0,H*.60,W,D,H*.52,0)
            for x in (-W*.40,-W*.10,W*.2,W*.42):
                for y in (-D*.29,D*.29):
                    box(x,y,H*.17,1.1,1.1,H*.34,0)
            for side in (-1,1):
                y=side*(D*.5+.025)
                box(W*.12,y,H*.60,W*.66,.06,H*.40,3)
                for n in range(27):
                    box(-W*.2+n/26*W*.66,side*D*.51,H*.60,.18,.62,H*.42,5)
                box(W*.13,side*D*.51,H*.60,W*.69,.68,.27,0)
                # Loggia glazing on the short elevations, within a thick white frame.
                box(side*(W*.5+.025),0,H*.60,.06,D*.68,H*.36,3)
                for n in range(6):
                    box(side*(W*.5+.16),(n/5-.5)*D*.67,H*.60,.34,.17,H*.40,5)
            # Flat garden terrace and dark recessed upper volume.
            box(0,0,H*.88,W*.98,D*.97,.20,6)
            box(-W*.08,D*.03,H*.955,W*.57,D*.48,H*.15,1)
            for side in (-1,1):
                box(0,side*D*.485,H*.90,W,.06,.65,3)
                box(0,side*D*.485,H*.919,W,.08,.08,4)

        elif osm_id == '201907981':
            box(0,0,H*.53,W*.94,D*.80,H*.94,0)
            box(0,0,H+.07,W*.95,D*.81,.14,6)
            for side in (-1,1):
                facade(side*D*.404,W*.9,H*.10,H*.87,9,13,False,5)
                for n in range(10):
                    box((n/9-.5)*W*.90,side*D*.426,H*.55,.34,.40,H*.90,5)
            # Glazed podium stays within this building's footprint.
            box(0,-D*.12,H*.07,W*.96,D*.73,H*.14,3)
            for n in range(3):
                box(0,-D*.12,H*.015+n*H*.055,W,D*.77,.22,5)
            for n in range(11):
                box((n/10-.5)*W*.93,-D*.486,H*.07,.11,.16,H*.14,5)

        elif osm_id == '1424900701':
            # Elevated upper gallery, recessed glass floor and V support on the slope.
            box(0,D*.20,H*.32,W*.35,D*.38,H*.64,2)
            box(0,D*.055,H*.40,W*.81,D*.77,H*.25,3)
            box(0,0,H*.765,W,D,H*.47,2)
            box(0,0,H+.06,W*.97,D*.97,.12,6)
            for x in (-W*.38,W*.38):
                beam((x,-D*.10,0),(x-W*.12,-D*.17,H*.52),.70,.85,2)
                beam((x,-D*.10,0),(x+W*.12,-D*.17,H*.52),.70,.85,2)
            for side in (-1,1):
                for n in range(17):
                    box((n/16-.5)*W*.8,side*D*.331,H*.40,.075,.12,H*.25,4)
            box(0,-D*.365,H*.28,W*.85,D*.13,.22,2)
            for n in range(24):
                box((n/23-.5)*W*.83,-D*.422,H*.309,.055,.055,H*.055,4)
            box(-W*.22,-D*.502,H*.79,W*.035,.09,H*.32,3)
            # Fine vertical formliner grooves, much shallower than window fins.
            for n in range(79):
                x=(n/78-.5)*W*.985
                box(x,-D*.502,H*.767,.023,.016,H*.43,1)
            # Stair set alongside the mass; low end is near the road.
            steps=22
            for n in range(steps):
                y=-D*.46+n*D*.75/steps
                top=.28+n*H*.022
                box(W*.45,y,top/2,W*.10,D*.78/steps,top,2)

        mesh = bpy.data.meshes.new(f'Photo landmark mesh / {osm_id}')
        mesh.from_pydata(verts, [], faces)
        mesh.materials.clear()
        for m in mats:
            mesh.materials.append(m)
        for p,i in zip(mesh.polygons,mi):
            p.material_index=i
        mesh.update()
        assert all(math.isfinite(v) for p in verts for v in p), osm_id
        ob=bpy.data.objects.new('Photo landmark / '+src.name,mesh)
        group.objects.link(ob)
        ob['osm_id']=osm_id
        ob['source_building']=src.name
        ob['photo_based']=True
        ob['landmark_rebuilt']=True
        ob['reference_url']=references[osm_id]['source_page']
        ob['reference_image_url']=references[osm_id]['image_url']
        ob['height_source']='OSM tag/levels or explicit photo-guided estimate; not surveyed'
        ob['height_m']=H
        ob['approximation_notes']=references[osm_id]['uncertainty']
        src.hide_render=True
        src.hide_set(True)
        src['photo_roof_anchor']=list(center+Vector((0,0,H+1)))
        stats['photo_landmarks']+=1
        stats['objects'].append({'osm_id':osm_id,'object':ob.name,'height_m':round(H,2),
                                 'source_world_min_z':round(low,3),
                                 'terrain_base_min_z':round(min(ground_samples),3) if ground_samples else None,
                                 'terrain_base_max_z':round(max(ground_samples),3) if ground_samples else None,
                                 'foundation_vertices_extended':len(extended_bases),
                                 'foundation_max_extension_m':round(max(extended_bases,default=0),3)})
        stats['vertices']+=len(verts)
        stats['faces']+=len(faces)
    return stats
