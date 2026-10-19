"""Publish measured validation and artifact entry points for the grading pass."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
a=json.loads((ROOT/'road_surface_v3_audit.json').read_text('utf-8'))
g=json.loads((ROOT/'road_grading_report.json').read_text('utf-8'))
n=json.loads((ROOT/'road_network_v3_report.json').read_text('utf-8'))['stats']
b=json.loads((ROOT/'building_terrain_alignment.json').read_text('utf-8'))
assert a['sampled_no_burial_pass'] and a['shared_node_height_pass'], 'Do not publish until actual mesh checks pass'
assert a['roads_with_fold_candidates']==0, 'Road surface folding remains'
text=f'''# 道路穿模与平整修正版

本轮按用户要求调整路面和周边地形，并继续在 Blender 中完成。最终修正与检查日期：2026年9月24日。

## 成果文件

- [可编辑主场景](CUHK_roads_graded.blend)
- [主渲染](CUHK_roads_graded_preview.png) · [建筑标签渲染](CUHK_roads_graded_labeled.png)
- [两处道路和基脚前后对照](road_grading_comparison.png)

## 已修改

1. 以官方0.5米DTM派生的1米显示网格替换旧的5米显示网格；模型有{g['terrain_vertices']:,}个地形顶点。官方无数据区保留旧地形，并记录有效数据掩码，未把补值标成新测量。
2. {n['profiles_with_official_xyz_matches']}条道路使用类型、方向和距离匹配的官方XYZ路径作为参考。保留源OSM共享节点及独立的上下层关系，修正桥头、平台和台阶附近的错误高程，约束不合理纵坡和急促反向折坡。
3. 路面按完整圆角面域重新三角化，插入真实路径节点，消除窄路急弯的翻折与重复端帽。路口采用共同平面过渡；1.5–7.5毫米显示偏移用于避免完全重叠面在渲染中闪烁，不属于测量精度。
4. 地面道路下方作局部填挖，桥面侵入处降低冲突坡面，周边以渐变边坡接回地形。路板具有独立的厚度与侧边；路口周围的路缘和中线停止，避免横穿交叉口。陈震夏宿舍低层立面前另作地形避让，清除道路边坡抬入窗格的局部土丘。
5. {sum(abs(r['vertical_shift_m'])>.01 for r in b)}处建筑基高随新裸地数据对齐，源楼体与对应外墙一起移动，楼高和外观保持原有建模依据，建筑标签重新排版。陈震夏宿舍的旧136米整块台地已纠正；官方地面路径约104–108米，上层连接另行保留。

## 实际网格检查

- 路面对象：{a['roads']}，含1450条地面道路与152条高架/正层级路线。
- 对实际路面设置{a['total_probes']:,}个检查点，其中{a['outside_terrain_probes']:,}个位于地形裁切边界外、不计入地形对照；范围内埋入超过5厘米的采样点为 **{a['buried_probe_count']}**。
- 最小采样路面—地形净距：{a['min_clearance_m']:.4f}米。该数是路面避免穿地的显示余量，不是桥下通行净空。
- 共享节点实际路面覆盖和高差检查：通过。
- 相邻三角投影反向的路面对象：**{a['roads_with_fold_candidates']}**。

完整检查：[road_surface_v3_audit.json](road_surface_v3_audit.json)。网络约束：[road_network_v3_report.json](road_network_v3_report.json)。地形调整：[road_grading_report.json](road_grading_report.json)。建筑基高：[building_terrain_alignment.json](building_terrain_alignment.json)。

近景复查：[同镜头前后对照与检查说明](ROAD_GRADING_RENDER_CHECK.md)。桥头端帽暗纹和宿舍最低层窗前土丘在新版实际渲染中已清除；局部地形避让记录见[foundation_clearance_report.json](foundation_clearance_report.json)。

仍需区分显示修正与实测设计：路网不含真实路面宽度和完整桥梁结构，保留的宽度、局部填挖、基础裙墙和桥板厚度均属于建模处理。道路采样无遮挡不等于工程净空认证。楼高仍包含前版估算，DTM格网间距也不能代替测量精度。

## 场景组织与复现

`04 Roads and paths`为可独立编辑的路面顶面；`14 Road slabs and edges`为路板侧面、底面和局部基础裙墙；地下和室内参考路径保留在隐藏的`12 Underground and indoor route references`；`10 Building labels / OSM names`为可编辑标签。

复现顺序：`prepare_road_network_v3.py` → `prepare_graded_terrain.py` → `prepare_road_grading.py` → `refine_foundation_clearance.py` → Blender运行`build_graded_roads.py` → `audit_road_surfaces_v3.py` → `render_graded_roads.py`。前后检查图由`render_road_grading_check.py`与`compose_road_grading_check.py`生成。

数据署名：香港特别行政区政府土木工程拓展署（CEDD 2020 LiDAR派生DTM）；地政总署（三维行人网络）；© OpenStreetMap contributors（道路、建筑轮廓和名称，ODbL）。原始数据、日期、基准和获取范围详见[数据来源记录](DETAILED_DATA_AND_ROADS.md)。
'''
(ROOT/'ROAD_GRADING.md').write_text(text,encoding='utf-8')
readme=ROOT/'README.md';old=readme.read_text('utf-8')
entry='\n最新道路与地形协调版：`CUHK_roads_graded.blend`。已接入1米派生地形、修正道路穿模与急弯翻折、调整路床边坡并重新对齐建筑基脚。最终渲染、实测网格检查和说明见 [ROAD_GRADING.md](ROAD_GRADING.md)。\n'
if '最新道路与地形协调版' not in old:readme.write_text(old.replace('\n','\n'+entry,1),encoding='utf-8')
print('ROAD_GRADING_DOC_COMPLETE')
