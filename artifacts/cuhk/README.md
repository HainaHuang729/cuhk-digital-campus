# 香港中文大学校园地形与建筑重建

Three.js 网页已升级为 Interactive Digital Campus：本机运行地址 <http://127.0.0.1:5178>，项目位于 `../../cuhk-campus-web`。支持建筑搜索与飞行定位、连续昼夜、校园故事、摄影，以及实例化树木和示意行人车辆。采用逸夫科学大楼高度修正版，继承道路与体育场平整成果；首屏地形/场地/建筑资源约24.06 MB，附近建筑按区域加载更高细节。详细用法见[网页说明](../../cuhk-campus-web/README.md)，检查结果见[网页验收](../../cuhk-campus-web/VERIFICATION.md)。

当前 Blender 模型：`CUHK_shaw_science_corrected.blend`。逸夫科学大楼主要屋面与两端屋顶结构按激光雷达校正，并重建五排彩色幕墙；上坡地形局部恢复。依据与限制见[逸夫科学大楼修正说明](SHAW_SCIENCE_CORRECTION.md)。之前各版本保留。

最新 UE5 渲染：已在本机 UE 5.8.2 完成4K校园总览，使用体育场平整版模型。成片、可编辑UE工程与执行记录见 [UE5成果](ue5/latest/README.md)。

最新体育场平整版：`CUHK_sports_leveled.blend`。两条跑道及内场、标线、球门已统一平面，外围人行道避让并复查。渲染与记录见 [SPORTS_LEVELING.md](SPORTS_LEVELING.md)。

最新道路与地形协调版：`CUHK_roads_graded.blend`。已接入1米派生地形、修正道路穿模与急弯翻折、调整路床边坡并重新对齐建筑基脚。最终渲染、实测网格检查和说明见 [ROAD_GRADING.md](ROAD_GRADING.md)。

最新道路连接修正版：`CUHK_connected_roads.blend`。已修正真实共享路口、闭合道路高程与地面遮挡；新增官方0.5米DTM/DSM、三维行人网和带照片纹理建筑小样。实际完成范围、残余问题和文件入口见 [DETAILED_DATA_AND_ROADS.md](DETAILED_DATA_AND_ROADS.md)。

最新照片参考重建版：`CUHK_photo_rebuilt.blend`。已按官方照片和校方设计图更新外观，并单独重建六栋地标；主图、全校园标签图、重点近景及逐栋来源见 [PHOTO_RECONSTRUCTION.md](PHOTO_RECONSTRUCTION.md)。本轮使用 Blender 渲染；UE5 已按用户要求暂停。

最新标注与平整道路版：`CUHK_labeled_smooth_roads.blend`；中文建筑标签、全校俯视图与道路平滑说明见 [LABELS_AND_ROADS.md](LABELS_AND_ROADS.md)。

最新精细版：`CUHK_refined.blend`，加入示意立面、屋顶、道路和运动场细节，以及依据地图林地标注布置的树木。详见 [REFINEMENT.md](REFINEMENT.md)，其中也说明了新增显示地形整平的范围与限制。

新增彩色材质版：`CUHK_color_materials.blend`，渲染图为 `CUHK_color_render.png`（3200×2800）。此版本使用示意性绿地、石材、陶土/青灰/铜绿屋顶、沥青与水面材质；颜色不代表实测外观，也不再代表高度来源。高度来源仍保存在每个对象的 `height_source` 属性中。下面的赭色/浅灰数据状态说明仅适用于原始体量版本。

打开 `CUHK_terrain_buildings.blend`。这是依据地理数据制作的可编辑校园体量模型，未重建建筑立面、门窗或实测屋顶。

## 模型内容

- 香港新界沙田的 CUHK 校园，地理裁切范围为 2.4 × 2.4 公里，包含邻近山坡和吐露港海岸。
- 481 × 481 个地形采样点，原始网格间距 5 米。水平、垂直均为 1:1 米制，无高程夸张。
- 205 处在 OSM 校园边界内或其 20 米邻域中的建筑轮廓，以及 165 处附近建筑参照；复合建筑可能拆为多个对象。
- 校内 5 处有 OSM 高度标注，60 处有楼层数（每层按 3.3 米换算），140 处缺少高度与楼层信息，按建筑用途估算。
- 赭色表示校内估算高度，浅灰表示具有高度或楼层标注，外围建筑使用灰绿色。颜色表示数据状态，不代表真实外墙颜色。
- 道路、步道、运动场、水体及实际海岸线；鸟瞰和正北朝上的俯视相机；500 米比例尺与北箭头。
- 每栋建筑具有独立对象、OSM ID、名称、原始标签、建模高度、高度来源和地基高程属性。完整清单见 `building_inventory.json`。

## 坐标和精度

Blender X 向东，Y 向北，Z 向上。局部原点为香港 1980 方格网（EPSG:2326）的 E=839400、N=831150 米。高程采用香港主水平基准（HKPD），不能直接视为 GPS 椭球高程。

地政总署公布的 DTM 精度约 ±5 米，包含架空道路、桥梁等非地面信息；植被区域可能表现为植被高度。显示地形采用 3×3 邻域平滑减轻栅格台阶，原始裁切保存在 `terrain.npz`。地形包 HTTP Last-Modified 为 2023-09-14，不能据此推断全部地形的测量年份。

建筑地基取轮廓采样高程的第 25 百分位值，是地形贴合近似。在陡坡、挡土墙、架空层、植被遮挡或多标高入口处可能出现局部埋入。建筑高度主要是估算，不具备测绘、工程设计或精确日照分析的可靠性。OSM 建筑覆盖度和边界不保证包含校园所有新建或附属设施。

道路表面随显示地形起伏；桥梁、立交及楼梯未做完整结构重建。运动场、水池和建筑屋顶均为简化体量。没有凭空添加建筑门窗、树木位置或照片贴图。

## 数据来源与署名

获取日期：2026-09-07。OSM 数据快照时间写入 `geodata.json` 及 Blender 场景属性。

- 地形：香港特别行政区政府地政总署，Digital Terrain Model，https://data.gov.hk/en-data/dataset/hk-landsd-openmap-5m-grid-dtm
- DTM 规格：https://www.landsd.gov.hk/en/spatial-data/open-data/kf_dtm.html
- 原始地形压缩包：https://www.landsd.gov.hk/landsd_psi_data/SMO/data/Whole_HK_DTM_5m.zip
- 建筑、道路、水体及海岸线：© OpenStreetMap contributors，ODbL，https://www.openstreetmap.org/copyright
- OSM 校园边界关系：https://www.openstreetmap.org/relation/7802779

本目录的地理提取数据含 OSM 派生数据，使用或再分发时须保留相关署名并遵守 ODbL。政府地形数据使用条件以其来源页面为准。

## 文件与复现

- `CUHK_terrain_buildings.blend`：可编辑场景，已保存鸟瞰相机为默认相机。
- `CUHK_overview.png`、`CUHK_topographic_plan.png`：最终渲染预览。
- `terrain.npz`：原始地形裁切；`geodata.json`：转换为局部坐标的原始地理特征；`meshes.json`：三角化后的平面几何。
- `building_inventory.json`、`stats.json`：建筑高度来源和统计。
- `prepare_data.py`：使用 numpy、pyproj、shapely 处理原始 GIS 数据。原始下载缓存在 `C:/Users/Amadeus/.agent-reach/cuhk/`，数据准备脚本依赖此缓存。
- `build_cuhk.py`：使用 Blender 自带 bpy、bmesh、numpy 建模并渲染。仅重建 Blender 场景时不需要网络或 GIS 依赖。

在本目录运行：

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python-exit-code 1 --python build_cuhk.py
```

已检查坐标转换、校园边界面积、地形裁切尺寸、高度取值及实际渲染。模型按数据来源区分实测标注和估算，不能将所有建筑视为实测重建。
