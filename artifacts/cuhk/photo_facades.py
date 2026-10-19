"""Reference-guided campus facades. Unseen elevations remain explicit approximations."""
import bpy, bmesh, json, math
from mathutils import Vector
from detail_buildings import _material

Z=Vector((0,0,1))

def linear_hex(value, default='#c9ccc6'):
    s=value or default
    rgb=[int(s.lstrip('#')[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb)

class Builder:
    def __init__(self): self.vertices=[]; self.faces=[]; self.indices=[]
    def face(self, points, material):
        n=len(self.vertices);self.vertices.extend(tuple(p) for p in points)
        self.faces.append(tuple(range(n,n+len(points))));self.indices.append(material)
    def panel(self,c,u,n,w,h,mat):
        self.face([c-u*w/2-Z*h/2,c+u*w/2-Z*h/2,c+u*w/2+Z*h/2,c-u*w/2+Z*h/2],mat)
    def box(self,c,u,n,w,d,h,mat):
        k=len(self.vertices)
        for zz in (-1,1):
            for xx,yy in ((-1,-1),(1,-1),(1,1),(-1,1)):
                self.vertices.append(tuple(c+u*(xx*w/2)+n*(yy*d/2)+Z*(zz*h/2)))
        for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            self.faces.append(tuple(k+i for i in f));self.indices.append(mat)
    def cylinder(self,c,r,h,mat,segments=24):
        low=[c+Vector((r*math.cos(i*math.tau/segments),r*math.sin(i*math.tau/segments),-h/2)) for i in range(segments)]
        high=[p+Z*h for p in low]
        self.face(list(reversed(low)),mat);self.face(high,mat)
        for i in range(segments):self.face([low[i],low[(i+1)%segments],high[(i+1)%segments],high[i]],mat)
    def beam(self,a,b,width,depth,mat):
        along=(b-a).normalized();u=along.cross(Z)
        if u.length<.01:u=Vector((1,0,0))
        u.normalize();n=along.cross(u).normalized();v=[]
        for end in (a,b):
            v.extend(end+u*x*width/2+n*y*depth/2 for x,y in ((-1,-1),(1,-1),(1,1),(-1,1)))
        for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):self.face([v[i] for i in f],mat)
    def arch(self,c,u,n,rise,mat):
        pts=[c-u*rise-Z*1.8,c+u*rise-Z*1.8]
        pts.extend(c+u*(rise*math.cos(i*math.pi/18))+Z*(rise*math.sin(i*math.pi/18)) for i in range(19))
        self.face(pts,mat)
        for i in range(18):
            aa=i*math.pi/18;bb=(i+1)*math.pi/18
            self.face([c+u*(r*math.cos(t))+Z*(r*math.sin(t)) for r,t in ((rise,aa),(rise+.2,aa),(rise+.2,bb),(rise,bb))],0)
    def finish(self,name,group,mats):
        mesh=bpy.data.meshes.new(name);mesh.from_pydata(self.vertices,[],self.faces);mesh.update()
        for m in mats:mesh.materials.append(m)
        for p,i in zip(mesh.polygons,self.indices):p.material_index=i
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
        ob=bpy.data.objects.new(name,mesh);group.objects.link(ob);return ob

def walls_of(source):
    pts=[source.matrix_world@v.co for v in source.data.vertices]
    result=[]
    for p in source.data.polygons:
        if abs(p.normal.z)>.02 or len(p.vertices)!=4:continue
        a,b=sorted((pts[i] for i in p.vertices),key=lambda v:v.z)[:2]
        u=b-a;u.z=0;w=u.length
        if w<1:continue
        u.normalize();n=source.matrix_world.to_3x3()@p.normal;n.normalize()
        if u.cross(Z).dot(n)<0:a,b=b,a;u=-u
        result.append((a.copy(),u,n,w,min(pts[i].z for i in p.vertices),max(pts[i].z for i in p.vertices)))
    return result

def apply_photo_facades(group,sources,mapping):
    records=[]
    for row in mapping:
        oid=str(row['osm_id']);source=sources.get(oid)
        notes=row.get('appearance_notes') or {}
        if isinstance(notes,str):notes={'notes':notes}
        scope=notes.get('scope','')
        if not source or not row.get('visually_inspected') or not (scope.startswith('exterior') or scope in ('courtyard_exterior','design_render','distant_complex','distant_exterior')):
            records.append({'osm_id':oid,'status':'unverified_exterior','photo_url':row.get('photo_url')});continue
        style=notes.get('facade','grid'); text=notes.get('notes','').lower()
        if oid=='135193165' and source.get('height_source')=='estimated':
            lo=min(v.co.z for v in source.data.vertices);hi=max(v.co.z for v in source.data.vertices)
            for v in source.data.vertices:v.co.z=lo+(v.co.z-lo)*33/(hi-lo)
            source.data.update();source['height_m']=33.;source['photo_height_note']='Official hostel text states ten storeys; 3.3m/storey is an estimate.'
        wall=_material('Photo_'+oid+'_Wall',linear_hex(notes.get('wall_hex')), .82)
        accent=_material('Photo_'+oid+'_Accent',linear_hex(notes.get('accent_hex'),'#858c89'),.7)
        glass=_material('Photo_ShadowGlazing',(.038,.076,.088),.24,.15)
        metal=_material('Photo_Aluminium',(.18,.205,.21),.42,.6)
        roof=_material('Photo_FlatConcreteRoof',(.30,.32,.29),.86)
        tile=_material('Photo_TerracottaTile',(.36,.145,.075),.78)
        orange=_material('Photo_OrangeFacadeFins',linear_hex('#df793c'),.63)
        lime=_material('Photo_LimeFacadeFins',linear_hex('#b6c548'),.63)
        oldmats=list(source.data.materials)
        source.data.materials.clear();source.data.materials.append(wall);source.data.materials.append(roof)
        for p in source.data.polygons:p.material_index=1 if p.normal.z>.5 else 0
        source['photo_reference']=row.get('photo_url') or row.get('source_page') or ''
        source['photo_reference_scope']=scope
        source['photo_observations']=notes.get('notes','')
        source['facade_reconstruction']='Visible architectural vocabulary from referenced photo; repeated layout on unseen elevations and dimensions approximate. OSM footprint/height retained.'
        for old in bpy.data.collections.get('07 Building details / illustrative',[]).objects:
            if str(old.get('osm_id'))==oid:old.hide_render=True;old.hide_viewport=True
        b=Builder();walls=walls_of(source)
        if not walls:continue
        if style=='red_column_green_pavilion':
            points=sorted({(round(a.x,5),round(a.y,5)) for a,_,_,_,_,_ in walls})
            center=Vector((sum(p[0] for p in points)/len(points),sum(p[1] for p in points)/len(points),min(w[4] for w in walls)))
            points=sorted([Vector((x,y,center.z))-center for x,y in points],key=lambda v:math.atan2(v.y,v.x))
            for i,p in enumerate(points):
                q=points[(i+1)%len(points)]
                b.face([center+p,center+q,center+q+Z*.24,center+p+Z*.24],4)
                c=center+p*.76+Z*1.72;b.cylinder(c,.145,3,0)
                rings=((1.09,3.33),(1.02,3.18),(.57,4.03),(.035,4.7))
                for (r,z),(rr,zz) in zip(rings,rings[1:]):
                    b.face([center+p*r+Z*z,center+q*r+Z*z,center+q*rr+Z*zz,center+p*rr+Z*zz],1)
            b.face([center+p+Z*.24 for p in points],4)
            b.cylinder(center+Z*4.79,.11,.38,1)
            ob=b.finish('Photo / '+source.name,group,[wall,accent,glass,metal,roof,tile,orange,lime])
            ob['osm_id']=oid;ob['source_building']=source.name;ob['photo_based']=True;ob['reference_url']=source['photo_reference'];ob['uncertainty']='Pavilion observed only in distant official aerial; 4.9m height and column positions estimated.'
            source.hide_render=True;source.hide_set(True);source['photo_roof_anchor']=list(center+Z*5)
            records.append({'osm_id':oid,'name':row.get('name_zh'),'status':'photo_guided_facade','scope':scope,'facade_style':style,'photo_url':row.get('photo_url'),'source_page':row.get('source_page'),'observations':notes.get('notes'),'geometry_vertices':len(b.vertices),'height_estimate_m':4.9})
            continue
        open_base=0
        if 'v_pilotis' in style:
            original_low=min(v.co.z for v in source.data.vertices)
            open_base=min(6.8,source.get('height_m',20)*.2)
            for v in source.data.vertices:
                if v.co.z<original_low+.05:v.co.z+=open_base
            source.data.update();walls=walls_of(source)
            for a,u,n,w,low,high in walls:
                for k in range(max(1,int(w/10))):
                    c=a+u*(w*(k+.5)/max(1,int(w/10)))-n*.8;c.z=low-open_base
                    b.beam(c,c-u*2+Z*open_base,.55,.7,0);b.beam(c,c+u*2+Z*open_base,.55,.7,0)
        h=max(v.co.z for v in source.data.vertices)-min(v.co.z for v in source.data.vertices)
        if 'facade_base_hkpd_m' in source:
            walls=[(a,u,n,w,max(low,float(source['facade_base_hkpd_m'])),high) for a,u,n,w,low,high in walls]
            h=max(w[5] for w in walls)-min(w[4] for w in walls)
        tags=json.loads(source.get('osm_tags','{}'))
        floor_hint=notes.get('visible_floor_count') or notes.get('visible_storeys')
        try: floors=int(float(source.get('facade_storeys') or tags.get('building:levels') or floor_hint or h/3.4))
        except (ValueError,TypeError):floors=round(h/3.4)
        floors=max(1,min(floors, max(1,round(h/2.5)),35));storey=h/floors
        # These categories describe visible construction, not typological randomization.
        blank=any(k in style for k in ('blank','minimal','auditorium','low_hall','faceted','central_box'))
        curtain=any(k in style for k in ('curtain','colorful_glass','reflective','glass_facade','glass_portal','glass_courtyard'))
        slits=any(k in style for k in ('slit','fins','vertical','deep_','library_vertical'))
        bands=any(k in style for k in ('band','ribbon','grid','frame','science','horizontal','blue_core','pink_','louvre','window_boxes'))
        balcony=any(k in style for k in ('balcon','corridor','residence_tile','zigzag_stair'))
        hood=any(k in style for k in ('hood','residence','dormitory','pastel','courtyard'))
        modules=0
        for a,u,n,w,low,high in walls:
            c=a+u*w/2;c.z=high+.25
            b.box(c-n*.12,u,n,w,.34,.5,0)
            if w<2.4:continue
            bays=max(1,round((w-.9)/(2.3 if slits else 3.4)))
            pitch=(w-1)/bays
            if blank:
                c=a+u*w/2+n*.035;c.z=low+min(3.4,h*.35)
                b.panel(c,u,n,w*.68,min(2.8,h*.2),2)
                if 'auditorium' in style:
                    for k in range(max(1,int(w/.42))):
                        q=a+u*(.25+k*.42)+n*.09;q.z=low+h*.52
                        b.box(q,u,n,.14,.15,h*.23,1)
                    c.z=high-.4;b.box(c+n*1.1,u,n,w,2.7,.85,0)
                elif 'central_box' in style and w>12:
                    for s in (-1,1):
                        q=a+u*(w/2+s*w*.13)+n*.15;q.z=low+h*.72;b.panel(q,u,n,1.1,1.2,2)
                elif 'low_hall' in style:
                    c.z=high-1.2;b.box(c,u,n,w,.3,1.4,1)
                continue
            for level in range(floors):
                z=low+(level+.55)*storey
                if curtain:
                    c=a+u*w/2+n*.08;c.z=z;b.panel(c,u,n,w-.3,storey-.13,2)
                    c.z=low+level*storey;b.box(c+n*.09,u,n,w,.18,.15,3)
                elif bands or balcony:
                    c=a+u*w/2+n*.04;c.z=z;b.panel(c,u,n,w-.7,storey*(.62 if balcony else .54),2)
                    c.z=low+level*storey+.16
                    b.box(c+n*(.65 if balcony else .12),u,n,w,1.5 if balcony else .38,.26 if balcony else .34,0)
                    if 'multicolor_balcony' in style:
                        for k in range(bays):
                            p=c+u*((k+.5)*pitch-w/2+.5)+n*.4-Z*.14
                            b.box(p,u,n,pitch*.91,1.25,.05,(1,6,7,2)[(k+level)%4])
                    if any(k in style for k in ('pink','pastel','blue_core','brick','residence_band')):
                        c.z=low+level*storey+storey*.24;b.panel(c+n*.22,u,n,w-.7,storey*.25,1)
                    if balcony:
                        c.z=low+level*storey+1.2;b.box(c+n*1.32,u,n,w,.1,.09,3)
                        c.z-=.45;b.panel(c+n*1.29,u,n,w,.78,1)
                for bay in range(bays):
                    c=a+u*(.5+(bay+.5)*pitch)+n*.08;c.z=z
                    if not (bands or balcony or curtain):
                        ww=pitch*float(notes.get('window_ratio') or (.3 if slits else .64));wh=min(storey*.61,2.15)
                        b.panel(c,u,n,ww,wh,2)
                        if hood:
                            b.box(c+Z*(wh/2+.1)+n*.23,u,n,ww+.2,.55,.14,0)
                            b.box(c-Z*(wh/2+.1)+n*.12,u,n,ww+.12,.34,.12,1)
                    if curtain:
                        b.box(c+n*.045,u,n,.065,.12,storey,3)
                        if 'colorful' in style:
                            # Fixed alternating observed palette; exact panel positions are estimates.
                            b.box(c+n*.17,u,n,.21,.45,storey*.91,(1,6,7)[(bay+level//3)%3])
                    elif bands or balcony:
                        b.box(c+n*.07,u,n,.17,.28,storey*.8,0)
                    else:
                        b.panel(c+n*.008,u,n,.055,min(storey*.61,2.15),3)
                    modules+=1
            if slits or 'frame' in style or balcony:
                # Real depth produces shadowed fins, unlike the former flat repeated windows.
                for bay in range(bays+1):
                    c=a+u*(.5+bay*pitch)+n*(.34 if slits else .13);c.z=(low+high)/2
                    b.box(c,u,n,.18 if slits else .30,.78 if slits else .36,h-.3,0)
            if 'tile' in style or 'pitched-tile' in text:
                c=a+u*w/2;c.z=high+.46;b.box(c-n*.65,u,n,w,1.65,.38,5)
            if 'hoods_and_vertical' in style or 'blue_core' in style:
                c=a+u*w*.16+n*.13;c.z=(high+low)/2;b.panel(c,u,n,min(w*.15,3.7),h-.4,1)
            if 'projecting_roof_boxes' in style and w>15:
                for s in (.20,.5,.8):
                    c=a+u*w*s-n*1.3;c.z=high-1
                    b.box(c,u,n,min(w*.17,6),3.4,2.6,0)
                    b.panel(c+n*1.71,u,n,min(w*.14,5),.65,2)
            if 'arch' in style and w>9:
                for k in range(max(1,int(w/5.8))):
                    c=a+u*(2.9+k*5.8)+n*.18;c.z=low+2.1
                    b.arch(c,u,n,1.25,2)
            if any(k in style for k in ('portal','perimeter','oversized_frames')):
                for x in (.55,w-.55):
                    c=a+u*x+n*.25;c.z=(low+high)/2;b.box(c,u,n,.9,.7,h,1 if 'oversized' in style else 0)
                c=a+u*w/2+n*.25;c.z=high-.5;b.box(c,u,n,w,.7,1,1 if 'oversized' in style else 0)
                if 'oversized' in style:
                    for level in range(2,floors,2):
                        c.z=low+level*storey;b.box(c,u,n,w,.8,.55,1)
            if 'white_window_boxes' in style:
                for level in range(floors):
                    c=a+u*w/2+n*.23;c.z=low+level*storey+.15;b.box(c,u,n,w-1.2,.47,.2,8)
                for k in range(bays+1):
                    c=a+u*(.6+k*(w-1.2)/bays)+n*.23;c.z=(low+high)/2;b.box(c,u,n,.18,.47,h-.8,8)
        if 'cylinder' in style and walls:
            a,u,n,w,low,high=max(walls,key=lambda q:q[3])
            radius=min(3.9,w*.1);c=a+u*w*.28+n*radius*.45;c.z=(low+high)/2
            b.cylinder(c,radius,h+1,1 if 'yellow' in style else 0)
            for i in range(1,floors):
                d=c.copy();d.z=low+i*storey;b.cylinder(d,radius+.06,.12,0)
        if notes.get('roof_style') in ('pitched','hipped'):
            # A subdivided pitch follows the recorded footprint, including courtyard holes.
            # Ridge axis/height are explicitly approximate from the single photograph.
            a,u,n,w,low,high=max(walls,key=lambda q:q[3]);pts=[source.matrix_world@v.co for v in source.data.vertices]
            ridge_n=n.copy();values=[p.dot(ridge_n) for p in pts];mid=(min(values)+max(values))/2;half=max(.1,(max(values)-min(values))/2);rise=min(3.2,half*.4)
            def elevated(p):
                q=p.copy();q.z=high+.06+rise*max(0,1-abs(p.dot(ridge_n)-mid)/half);return q
            roofmat=5 if any(s in text for s in ('red','terracotta','orange','tile')) else 0
            source.data.calc_loop_triangles()
            for tri in source.data.loop_triangles:
                if source.data.polygons[tri.polygon_index].normal.z<.8:continue
                aa,bb,cc=[pts[i] for i in tri.vertices];cuts=max(2,min(24,math.ceil(max((aa-bb).length,(bb-cc).length,(cc-aa).length)/4)))
                def point(i,j):return elevated(aa+(bb-aa)*i/cuts+(cc-aa)*j/cuts)
                for i in range(cuts):
                    for j in range(cuts-i):
                        b.face([point(i,j),point(i+1,j),point(i,j+1)],roofmat)
                        if i+j<cuts-1:b.face([point(i+1,j),point(i+1,j+1),point(i,j+1)],roofmat)
            for a,u,n,w,low,high in walls:
                p=a.copy();p.z=high;q=p+u*w
                for k in range(8):
                    p1=p+(q-p)*k/8;p2=p+(q-p)*(k+1)/8;b.face([p1,p2,elevated(p2),elevated(p1)],0)
        white=_material('Photo_WhiteFacadeFrames',linear_hex('#e3e5df'),.78)
        ob=b.finish('Photo / '+source.name,group,[wall,accent,glass,metal,roof,tile,orange,lime,white])
        ob['osm_id']=oid;ob['source_building']=source.name;ob['photo_based']=True
        ob['reference_url']=source['photo_reference'];ob['observed_features']=notes.get('notes','')
        ob['uncertainty']='Facade module dimensions, repetitions, unphotographed sides, roof depths and hidden geometry are approximate; not photogrammetry.'
        records.append({'osm_id':oid,'name':row.get('name_zh') or row.get('name_en'),'status':'design_guided_facade' if scope=='design_render' else 'photo_guided_facade','scope':scope,'facade_style':style,'photo_url':row.get('photo_url'),'source_page':row.get('source_page'),'observations':notes.get('notes',''),'window_modules':modules,'floors_modeled':floors,'geometry_vertices':len(b.vertices)})
    return records
