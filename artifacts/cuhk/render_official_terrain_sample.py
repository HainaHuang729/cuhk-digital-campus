"""Show source photo-textured models on unmodified native 0.5 m CEDD DTM."""
import bpy,json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'CUHK_official_3d_sample.blend'))
scene=bpy.context.scene
for ob in list(bpy.data.objects):
    if ob.name.startswith('Context terrain /'):bpy.data.objects.remove(ob,do_unlink=True)
grid=np.load(ROOT/'official_terrain_05m_sample.npz');xs,ys,z=grid['x'],grid['y'],grid['elevation']
xx,yy=np.meshgrid(xs,ys);ny,nx=z.shape
verts=np.column_stack((xx.ravel(),yy.ravel(),z.ravel())).astype(np.float32)
a=(np.arange(ny-1)[:,None]*nx+np.arange(nx-1)).ravel()
faces=np.column_stack((a,a+nx,a+nx+1,a+1)).astype(np.int32)
mesh=bpy.data.meshes.new('CEDD native 0.5m DTM crop')
mesh.vertices.add(len(verts));mesh.vertices.foreach_set('co',verts.ravel())
mesh.loops.add(faces.size);mesh.loops.foreach_set('vertex_index',faces.ravel())
mesh.polygons.add(len(faces));mesh.polygons.foreach_set('loop_start',np.arange(len(faces),dtype=np.int32)*4);mesh.polygons.foreach_set('loop_total',np.full(len(faces),4,dtype=np.int32));mesh.update()
ob=bpy.data.objects.new('Official terrain / 0.5m DTM, native HKPD elevation',mesh);scene.collection.objects.link(ob)
mat=bpy.data.materials.new('Terrain / display sage');mat.diffuse_color=(.30,.38,.24,1);mat.use_nodes=True
bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');bsdf.inputs['Base Color'].default_value=(.30,.38,.24,1);bsdf.inputs['Roughness'].default_value=.94
mesh.materials.append(mat)
for p in mesh.polygons:p.use_smooth=True
report=json.loads((ROOT/'official_terrain_05m_sample_report.json').read_text('utf-8'))
ob['source_record']=json.dumps(report,ensure_ascii=False);ob['geometry_note']='Unmodified raster centres, no smoothing, cut/fill or shrinkwrap.'
scene['source_attribution']='Buildings: Lands Department, HKSAR Government. Terrain: Civil Engineering and Development Department, HKSAR Government (2020 LiDAR-derived DTM).'
scene['sample_limitation']='Source dates differ; this is a georeferenced data sample, not a validated joined campus model. Hidden building substructures may extend below the DTM.'
scene.camera.data.ortho_scale*=1.16
scene.render.resolution_x=2000;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.filepath=str(ROOT/'CUHK_official_terrain_sample_preview.png')
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_official_terrain_sample.blend'))
bpy.ops.render.render(write_still=True)
print('OFFICIAL_TERRAIN_SAMPLE_COMPLETE',flush=True)
