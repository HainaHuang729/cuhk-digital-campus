# 逸夫科学大楼高度校正

2026-09-25。对象为逸夫科學大樓 / Run Run Shaw Science Building，校园 H34，OSM 107139044。

当前可编辑模型：`CUHK_shaw_science_corrected.blend`。Three.js 网页使用该模型重新导出；此前的 `CUHK_sports_leveled.blend` 保留。

## 依据

- [中大 2011 年命名公告](https://www.cpr.cuhk.edu.hk/tc/press/naming-ceremony-of-run-run-shaw-science-building-at-cuhk-held-today/)明确建筑共六层。[2007 年建筑获奖公告](https://www.cpr.cuhk.edu.hk/tc/press/cuhks-centralized-labs-wins-hong-kong-institute-of-architects-award/)说明五层为实验室。
- [中大建筑照片](https://www.cuhk.edu.hk/english/images/campus/photos/large/buildings/42.jpg)可见五排彩色玻璃幕墙、深色端部与屋顶设备屏风。
- 缓存的 CEDD 2020 年 0.5 米 DSM/DTM：主要屋面平台 3,574 个内侧样点中位数为 111.599 米 HKPD，5–95 百分位为 111.465–111.741 米；两端高位结构约 117.6 米。屋面中段没有与端部同样高的连续结构。

## 修正

旧模型只采用 OSM 的三层地上标签，遗漏另三层地下标签所表达的山坡建筑关系，再叠加基底对齐，得到 9.9 米楼高、90.649 米屋顶标高。现将主要屋面定到 111.6 米 HKPD，较旧模型提高 20.951 米。两端设备结构定到 117.6 米，采用 DSM 高位样点约束轮廓，并添加示意百叶。

以既有参考基底 80.749 米计算，主要屋面高约 30.85 米，含端部屋顶结构约 36.85 米。五排彩色幕墙从约 85.89 米起，以下为不透明基础/服务层；基础向坡下延伸至 71 米以避免悬空。**基底和楼层分隔是建模估算，36.9 米并非校方公布的实测总高。** DSM 能约束屋顶标高，不能独立确定室内楼层高度和设备细部。

上坡后侧地形向原始 DTM 局部恢复，92–96 米高程条件及 5–15 米边缘距离均作平滑过渡。道路顶面外围 3 米内的地形顶点保持完全不变，3–8 米间渐变；下坡地形不变。道路与运动场对象的世界坐标哈希在修正前后一致。

## 文件

- `SHAW_SCIENCE_CORRECTION.json`：模型修改与高度记录。
- `audits/shaw_elevation_audit.json`、`shaw_elevation_diagnostics.png`：DSM/DTM 检查。
- `audits/shaw_terrain_restore_report.json`：局部地形与道路保护检查。
- `audits/shaw_road_clearance_audit.json`、`shaw_sports_planarity_audit.json`：保存后真实网格验证，道路穿模采样为0、11个运动面起伏为0。
- `audits/terrain_shaw_science_corrected_1m.npz`：显示地形。
- `correct_shaw_science.py`：从上一版 Blender 模型复现本次校正。
- 网页 `public/model/validation.json`：实际解码 GLB 后的屋顶、材质、建筑清单和跑道验证。

仅代表照片和高程辅助的外观重建，不是建筑施工图或完整实测模型。
