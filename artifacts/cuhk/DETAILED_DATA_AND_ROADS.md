# CUHK 更详细的数据与道路连接修正

核查与生成日期：2026-09-22。继续使用 Blender，UE5 保持暂停。

## 可打开的成果

- [道路连接修正版](CUHK_connected_roads.blend)：现有照片参考校园模型，重建共享路口和地面道路；含建筑标签。
- [主渲染](CUHK_connected_roads_preview.png)、[标签渲染](CUHK_connected_roads_labeled.png)。
- [官方照片纹理建筑小样](CUHK_official_3d_sample.blend)、[小样渲染](CUHK_official_3d_sample_preview.png)：9 个官方模型对象，纹理已打包；部分是同一建筑的组件，不能称为9栋已识别建筑。
- [官方建筑与0.5米地形对齐小样](CUHK_official_terrain_sample.blend)、[对齐渲染](CUHK_official_terrain_sample_preview.png)：167.5×307.5米原生0.5米DTM裁片，206,025个采样点，未整平、插值或改变高程。源模型与地形年代不同，保留了可见的交接误差，不代表已完成整校园融合。
- [道路局部前后检查图](road_continuity_comparison.png)：相同相机的 Blender 实际渲染；为观察路面隐藏植被与标签，具体设置见对照脚本。

## 已实际取得的数据

| 数据 | 本次获取状态 | 比旧模型多了什么 |
|---|---|---|
| CEDD 2020 LiDAR派生DTM与DSM | 覆盖目标范围的DTM24幅、DSM24幅，共225,325,546字节；48 ZIP全通过CRC和GeoTIFF像元检查 | 格网0.5米；旧地形格网5米。DTM描述裸地，DSM保留建筑/树木等表面，可辅助估计高度 |
| LandsD带纹理独立建筑模型 | 7-NE-17C图幅取得9个依赖完整的glTF对象，已实际导入Blender | 原始楼体几何、UV与照片纹理；目前仅International House 1已通过独立轮廓匹配确认名称，其余保留源ID及候选关系 |
| LandsD三维行人网络 | 窗口5,146段，其中官方CUHK场地子集2,545段，保留XYZ与属性 | 校园含315段楼梯、41段天桥、7段扶梯、1段升降机、186段室内路径 |
| TD第二代车行路网 | 344段中心线、255个路口、80段转向关联 | 路口与转向关系；几何为XY，ELEVATION字段是层级，不是米制海拔 |
| 2025真射影像TDOP | 中大核心图幅下载返回200和有效ZIP前缀，尚未下载完整520MB图幅 | 2025-01-03照片、0.25米GSD，可用于核对新道路边缘、屋顶和地面材质 |

0.5米是栅格间距，**没有核实到2020栅格的定量垂直精度保证**。DTM采用HK1980方格和HKPD高程。官方行人网络元数据标注XY准确度1米、Z准确度2米；它没有在本次获取的元数据中明确垂直基准，需共同地面点检核，不能仅凭平面CRS认定Z基准。

完整原始数据保留在 [C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922](C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922)，详细来源与实际下载层级见 [数据获取报告](C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922/DATA_SOURCES.md)、[道路数据报告](C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922/roads/README.md)。48个地形ZIP已经完整落盘；建筑整图幅、原始LAS和实景网格整图幅尚未全部下载。主校园模型仍使用旧5米显示地形和已有示意建筑；新数据已经取得并做局部导入，未冒充全校已替换。

补充地面高程对照：排除特殊通道、建筑附近和CEDD同源高程后，437个普通室外地面候选点的“官方路径Z−新DTM”中位数−0.026米，IQR1.541米，P95绝对差4.290米。支持整体高程大致一致，但仍存在约±10米离群，不能据此正式确认HKPD或给所有道路套用同一个偏移。[逐点高程检查](C:/Users/Amadeus/.agent-reach/cuhk/high_detail_20260922/roads/GROUND_Z_CHECK.md)。

## 道路为什么看起来不连续

1. 旧高程脚本用“XY+layer”作为连接键，同一OSM节点在真实桥头改变layer时被拆开，已知连接最大高差约13.4米。现在按原始OSM节点身份统一高程，同时保留125处跨层或语义不确定的交叉。
2. 路面边缘会被地形遮住。现在以完整路面三角形约束地面道路下方的显示地形，再生成路口过渡和圆端连接。
3. 本轮检查还修复了24条闭合路线的采样问题：采用有序累计里程，避免把环路最后一点投影到起点而错误降低整段高程。加入闭环里程及端点高度断言。

未按空间接近直接粘连不同道路；没有凭空添加未绘制路线。16个相邻端点候选保留待核实。地下、室内等78条路线保留在隐藏参考集合；不能把它们画在地面上当作已修复通路。

## 实际检查结果

| 检查 | 结果 |
|---|---|
| 真实共享节点连接 | 1,874个共享节点、2,571对连接；输出高程差小于0.00001米，实际路面高度函数在共享点最大差0.00000000米 |
| 地面道路 | 1450条；0条在抽样检查中发现埋入地形超过5厘米 |
| 高架/正层级路线 | 152条；33条仍有局部地形相交，需要逐处用官方高程/结构核对 |
| 所有道路被地形遮挡的估算面积 | 约11,886平方米 → 约253平方米；为网格抽样估算，前后路线分类/网格有变化，并非精确同面积测量 |
| 新增显示地形切深 | 变化单元平均0.55米、最大17.52米；仅属旧显示地形修补，不是实测挖填方 |

遮挡检查在实际Blend文件中对每个路面三角形取中心及三条边中点，和显示地形三角形比较；本次共1,222,928个探针。它检查地形遮挡，不证明桥梁净空、室内可达性或完整道路面无缝融合。`max_shared_junction_gap_m`在更早的旧脚本中曾是固定0，不能视为实测通过；本报告以重新诊断及实际采样为依据。

仍有局部几何不可信：最大显示切深发生在局部坐标(-255,240)陈震夏宿舍附近的地面/负层级入口连接处，来自旧平台与入口高程矛盾，不能把17.52米切口当真实地形。残余高架/正层级遮挡对象已链接到Blend集合`13 Road levels to verify`，每条对象都保留抽样数量、最小净距与问题说明，便于接入真实高程时逐处处理。

诊断数据：[road_network_audit.json](road_network_audit.json)、[road_surface_before.json](road_surface_before.json)、[road_surface_after.json](road_surface_after.json)、[connected_roads_report.json](connected_roads_report.json)。复现：先运行`repair_road_network.py`，再用Blender运行`rebuild_connected_roads.py`，最后运行`audit_road_surfaces.py -- CUHK_connected_roads.blend`和`tag_road_quality.py`。

## 下一层细化的依据

完整升级应先将0.5米DTM/DSM拼接并核对建筑平台，再逐图幅导入官方建筑几何与纹理，按真实XYZ行人路径区分地面、台阶、天桥和室内通道。道路中心线不包含真实路面边界、宽度、踏步尺寸；这些需正射影像、道路边线或局部点云补足。官方iB1000路面查询本次失败，未取得路面面域。原始LAS平台需验证码会话；街景MMS点云有覆盖但实际数据收费申请，均未取得实际文件。

## 官方出处与署名

- 地形：香港特别行政区政府土木工程拓展署，[CEDD LiDAR](https://www.ginfo.cedd.gov.hk/geoopendata/eng/LIDAR.aspx)、[2020元数据](https://www.ginfo.cedd.gov.hk/geoopendata/Data/LiDAR/2020%20LiDAR.xml)。
- 建筑：香港特别行政区政府地政总署，[独立三维模型目录](https://portal.csdi.gov.hk/csdi-webpage/dataset/landsd_rcd_1671676915450_88604)、[3D地图产品](https://www.landsd.gov.hk/en/survey-mapping/mapping/3d-mapping.html)。
- 三维路径：[LandsD 3D Pedestrian Network](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-3d-pedestrian-network)。
- 车行路：[TD第二代道路网络](https://data.gov.hk/en-data/dataset/hk-td-tis_15-road-network-v2)。
- 影像：[官方产品规格](https://www.landsd.gov.hk/en/survey-mapping/mapping/aerial-photo-photogrammetric-products/digital-orthophoto.html)、[摄影日期表](https://www.landsd.gov.hk/doc/en/mapping/digital-map/common/update/tdop_update.csv)。
- 现有校园和道路模型含 © OpenStreetMap contributors 数据，[ODbL署名](https://www.openstreetmap.org/copyright)。

模型宽度、桥面结构和旧楼体估算高度仍含建模假设；政府数据的取得不等于整个场景已达到测绘级精度。
