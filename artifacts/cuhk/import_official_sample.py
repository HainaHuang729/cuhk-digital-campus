"""Native Blender glTF sample import. Full source node matrices are left intact."""
import bpy
import json
from pathlib import Path

import numpy as np
from mathutils import Matrix,Vector

ROOT=Path(__file__).resolve().parent
CACHE=Path.home()/'.agent-reach/cuhk/high_detail_20260922'
ORIGIN=np.array([839400.,831150.,0.])


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene=bpy.context.scene
    scene.unit_settings.system='METRIC'
    scene.unit_settings.scale_length=1
    inventory=json.loads((CACHE/'individual_sample_inventory.json').read_text('utf-8'))
    report=[]
    for item in inventory:
        if not item['complete']:continue
        path=Path(item['file'])
        source=json.loads(path.read_text('utf-8'))
        before=set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(path))
        imported=set(bpy.data.objects)-before
        group=bpy.data.collections.new('Official / '+item['id'])
        scene.collection.children.link(group)
        for obj in imported:
            for parent in list(obj.users_collection):parent.objects.unlink(obj)
            group.objects.link(obj)
        for obj in imported:
            if obj.parent not in imported:
                obj.matrix_world=Matrix.Translation(-Vector(ORIGIN))@obj.matrix_world
        bpy.context.view_layer.update()
        vertices=[];triangles=[];materials=set();images=set();face_count=0;triangle_count=0
        for obj in imported:
            obj['source_gltf']=str(path)
            obj['official_building_id']=item['id']
            obj['import_note']='Native glTF Y-up conversion; source root scale preserved, local translation subtracts HK1980 origin only.'
            if obj.type!='MESH':continue
            mesh=obj.data
            co=np.asarray([obj.matrix_world@v.co for v in mesh.vertices],dtype=np.float64)
            vertices.extend(co.tolist());face_count+=len(mesh.polygons)
            mesh.calc_loop_triangles();triangle_count+=len(mesh.loop_triangles)
            for tri in mesh.loop_triangles:
                pts=co[list(tri.vertices),:2]
                area=abs(np.cross(pts[1]-pts[0],pts[2]-pts[0]))*.5
                if area>1e-5:triangles.append(pts.tolist())
            for mat in mesh.materials:
                if mat is None:continue
                materials.add(mat.name)
                if mat.use_nodes:
                    for node in mat.node_tree.nodes:
                        if node.type=='TEX_IMAGE' and node.image:
                            images.add(node.image)
        co=np.asarray(vertices)
        report.append(dict(id=item['id'],source_gltf=str(path),root_matrix_gltf=source['nodes'][0].get('matrix'),
                           source_root_scale=item['root_scale'],importer='Blender native bpy.ops.import_scene.gltf',
                           coordinate_conversion='glTF global XYZ=(East,elevation,-North) -> Blender global XYZ=(East,North,elevation); subtract (839400,831150,0) metres',
                           local_bounds_min=co.min(axis=0).tolist(),local_bounds_max=co.max(axis=0).tolist(),dimensions_m=np.ptp(co,axis=0).tolist(),
                           vertices=len(co),polygons=face_count,triangles=triangle_count,mesh_objects=sum(o.type=='MESH' for o in imported),
                           materials=sorted(materials),textures=[dict(name=im.name,width=im.size[0],height=im.size[1],filepath=im.filepath) for im in images],
                           projected_triangles_xy=triangles))
    assert len(report)==9,len(report)
    assert all(len(r['textures'])>0 for r in report)
    assert all(1<max(r['dimensions_m'])<200 for r in report)
    assert all(-1200<r['local_bounds_min'][0]<1200 and -1200<r['local_bounds_min'][1]<1200 for r in report)
    bpy.ops.file.pack_all()
    scene['source']='Hong Kong Lands Department official textured individual-building glTF sample; source node matrices and scales preserved.'
    scene['geographic_origin_hk1980']='839400,831150,0'
    scene['README']='Independent 9-building import validation, not the full campus model. See official_3d_sample_report.json.'
    (ROOT/'official_3d_sample_import_geometry.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'CUHK_official_3d_sample.blend'))
    print('OFFICIAL_SAMPLE_IMPORTED',len(report),sum(r['triangles'] for r in report),flush=True)


if __name__=='__main__':main()
