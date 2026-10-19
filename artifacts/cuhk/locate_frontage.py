import bpy,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_roads_graded.blend'))
s=bpy.context.scene
for c in bpy.data.collections:
    if c.name.startswith(('09 ','10 ')):c.hide_viewport=True
bpy.context.view_layer.update()
target=Vector((-263,244,139));cam=target+Vector((-100,-25,72));rot=(target-cam).to_track_quat('-Z','Y');right=rot@Vector((1,0,0));up=rot@Vector((0,1,0));direction=rot@Vector((0,0,-1))
for x,y in [(875,850),(875,875),(875,900),(875,925),(855,900),(900,900)]:
    origin=cam+right*((x/1600-.5)*105)+up*((.5-y/1200)*105*1200/1600)
    hit,loc,normal,face,ob,matrix=s.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,direction,distance=2000)
    print(json.dumps({'pixel':[x,y],'object':ob.name if hit else None,'xyz':list(loc) if hit else None}),flush=True)
