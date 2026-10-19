"""Apply an illustrative architectural palette, save a new scene and render it."""
import bpy, json
from pathlib import Path
root=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(root/'CUHK_terrain_buildings.blend'))
scene=bpy.context.scene

def surface(name, low, high=None, scale=.5, bump=.04, roughness=.75, metallic=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*low,1)
    nodes=m.node_tree.nodes; nodes.clear(); links=m.node_tree.links
    bs=nodes.new('ShaderNodeBsdfPrincipled'); bs.inputs['Base Color'].default_value=(*low,1)
    bs.inputs['Roughness'].default_value=roughness; bs.inputs['Metallic'].default_value=metallic
    out=nodes.new('ShaderNodeOutputMaterial'); links.new(bs.outputs['BSDF'],out.inputs['Surface'])
    if high:
        geo=nodes.new('ShaderNodeNewGeometry'); noise=nodes.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value=scale; noise.inputs['Detail'].default_value=3
        links.new(geo.outputs['Position'],noise.inputs['Vector'])
        ramp=nodes.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.2; ramp.color_ramp.elements[0].color=(*low,1)
        ramp.color_ramp.elements[1].position=.8; ramp.color_ramp.elements[1].color=(*high,1)
        links.new(noise.outputs['Fac'],ramp.inputs['Fac']); links.new(ramp.outputs['Color'],bs.inputs['Base Color'])
        b=nodes.new('ShaderNodeBump'); b.inputs['Strength'].default_value=.3; b.inputs['Distance'].default_value=bump
        links.new(noise.outputs['Fac'],b.inputs['Height']); links.new(b.outputs['Normal'],bs.inputs['Normal'])
    return m

grass=surface('Landscape / variegated hillside greens',(.028,.105,.018),(.18,.30,.045),.034,.30)
asphalt=surface('Road / graphite asphalt',(.038,.046,.052),(.075,.085,.09),1.8,.025)
path=surface('Path / warm stone paving',(.38,.30,.18),(.62,.51,.32),.8,.035)
water=surface('Water / turquoise ripples',(.012,.12,.19),(.025,.34,.38),.13,.15,.22,.15)
pitch=surface('Pitch / emerald turf',(.015,.19,.045),(.045,.32,.09),.12,.015)
track=surface('Track / red rubber',(.40,.052,.019),(.61,.115,.037),1,.01)
plinth=surface('Plinth / dark blue slate',(.018,.032,.043),(.033,.056,.073),.06,.05)
walls=[
 surface('Facade / ivory limestone',(.63,.55,.39),(.82,.77,.61),.7,.025),
 surface('Facade / warm plaster',(.70,.59,.42),(.88,.79,.62),1,.018),
 surface('Facade / pale concrete',(.48,.53,.53),(.70,.74,.71),.8,.022),
 surface('Facade / muted red brick',(.34,.14,.074),(.49,.25,.14),.7,.018),
]
roofs=[
 surface('Roof / terracotta',(.35,.066,.022),(.59,.18,.062),.45,.055),
 surface('Roof / blue slate',(.035,.071,.095),(.09,.145,.17),.5,.035),
 surface('Roof / patinated copper',(.055,.20,.18),(.14,.32,.26),.2,.025,.48,.25),
 surface('Roof / weathered concrete',(.27,.30,.28),(.44,.46,.40),.6,.025),
]
context=surface('Context / pale sandstone',(.40,.38,.31),(.56,.54,.45),.8,.02)
building_count=0
for o in bpy.data.objects:
    if o.type!='MESH': continue
    if 'height_source' in o:
        campus=any(c.name=='02 Campus buildings' for c in o.users_collection)
        tags=json.loads(o['osm_tags']); seed=int(o['osm_id']); typ=tags.get('building','yes')
        wi=0 if typ=='university' else 1 if typ=='dormitory' else seed%3
        ri=0 if typ=='dormitory' else (seed%4)
        if tags.get('amenity')=='library': wi,ri=0,2
        if campus and typ not in ('university','dormitory') and seed%9==0: wi=3
        o.data.materials[0]=walls[wi] if campus else context
        if len(o.data.materials)>1: o.data.materials[1]=roofs[ri] if campus else roofs[3]
        o['appearance']='Illustrative palette; not surveyed facade or roof finishes'
        building_count+=1
    else:
        for i,m in enumerate(o.data.materials):
            replacement={'Topographic terrain':grass,'Roads':asphalt,'Footpaths and steps':path,'Mapped water':water,'Sports pitches':pitch,'Running tracks':track,'Map plinth':plinth}.get(m.name)
            if replacement: o.data.materials[i]=replacement

bpy.data.objects['Legend'].data.body='ILLUSTRATIVE MATERIAL PALETTE  /  HEIGHT SOURCES STORED IN OBJECT PROPERTIES'
bpy.data.objects['Title'].data.body='CUHK  /  HILLSIDE CAMPUS'
scene['appearance_note']='Colors and procedural materials are illustrative. Original geometry and height-source metadata retained.'
sun=bpy.data.objects['Sun / northwest']; sun.data.energy=3.0; sun.data.color=(1,.90,.74); sun.data.angle=.12
background=next(n for n in scene.world.node_tree.nodes if n.type=='BACKGROUND')
background.inputs[0].default_value=(.45,.55,.66,1); background.inputs[1].default_value=.45
scene.camera=bpy.data.objects['Camera / southeast overview']
scene.render.engine='CYCLES'; scene.cycles.samples=160; scene.cycles.use_adaptive_sampling=True; scene.cycles.adaptive_threshold=.012; scene.cycles.use_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type='OPTIX'; prefs.get_devices()
    if any(d.type=='OPTIX' for d in prefs.devices):
        for d in prefs.devices: d.use=d.type=='OPTIX'
        scene.cycles.device='GPU'
except Exception as e: print('CPU fallback',str(e),flush=True)
scene.view_settings.view_transform='AgX'; scene.view_settings.exposure=.15
scene.render.resolution_x=3200; scene.render.resolution_y=2800; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.render.image_settings.color_mode='RGB'
scene.render.filepath=str(root/'CUHK_color_render.png')
assert building_count==370
bpy.ops.wm.save_as_mainfile(filepath=str(root/'CUHK_color_materials.blend'))
bpy.ops.render.render(write_still=True)
print('COLOR_RENDER_COMPLETE',flush=True)
