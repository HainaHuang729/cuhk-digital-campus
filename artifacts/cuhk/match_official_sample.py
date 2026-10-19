"""Conservative footprint matching for the nine native-imported official building samples."""
import json,sys
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(Path.home()/'.agent-reach/cuhk/python'))
from shapely.geometry import shape,Polygon,mapping
from shapely.ops import unary_union

rows=json.loads((ROOT/'official_3d_sample_import_geometry.json').read_text('utf-8'))
buildings=[(f,shape(f['geometry'])) for f in json.loads((ROOT/'geodata.json').read_text('utf-8'))['features'] if f['kind']=='building']
for row in rows:
    footprint=unary_union([Polygon(t) for t in row.pop('projected_triangles_xy')]).buffer(0)
    candidates=[]
    for feature,geometry in buildings:
        distance=footprint.centroid.distance(geometry.centroid)
        if footprint.intersects(geometry) or distance<40:
            intersection=footprint.intersection(geometry).area
            union=footprint.union(geometry).area
            candidates.append(dict(osm_id=feature['id'],name_en=feature['tags'].get('name:en'),name_zh=feature['tags'].get('name:zh'),
                                   iou=intersection/union if union else 0.,sample_fraction_inside_osm=intersection/footprint.area,
                                   centroid_distance_m=distance))
    candidates.sort(key=lambda r:r['iou'],reverse=True)
    row['footprint_geometry']=mapping(footprint)
    row['footprint_area_m2']=footprint.area
    row['osm_candidates']=candidates[:3]
    best=candidates[0] if candidates else None
    if best and best['iou']>=.70 and best['centroid_distance_m']<5:
        row['name_match']=dict(status='high_confidence_footprint_match',**best)
    elif best and best['sample_fraction_inside_osm']>=.97 and best['name_en'] and best['iou']>=.04:
        row['name_match']=dict(status='spatial_component_of_named_osm_footprint',note='Projected imported component lies almost entirely within this named OSM footprint; individual component name is not independently verified.',**best)
    else:
        row['name_match']=dict(status='unconfirmed',note='Candidate proximity/overlap is insufficient to assign a building name.')
report=dict(created_utc=datetime.now(timezone.utc).isoformat(),sample_count=len(rows),source_provider='Hong Kong Lands Department individual textured 3D building models',
            source_archive_tile='7-NE-17C_GLTF.zip (locally verified complete entries only)',
            coordinate_system='Hong Kong 1980 Grid EPSG:2326; local origin (839400,831150,0) metres; Blender Z-up',
            import_method='Blender 5.2 native glTF importer honors all glTF root matrices including two 0.0254 unit scales; only the local origin translation is applied afterwards.',
            geometry_is_official=True,facade_materials_are_source_textures=True,
            naming_note='OSM association is independently measured in XY. Unconfirmed candidates are not presented as identified buildings.',
            total_mesh_objects=sum(r['mesh_objects'] for r in rows),total_vertices=sum(r['vertices'] for r in rows),
            total_polygons=sum(r['polygons'] for r in rows),total_triangles=sum(r['triangles'] for r in rows),
            models=rows)
(ROOT/'official_3d_sample_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='models'},ensure_ascii=True))
