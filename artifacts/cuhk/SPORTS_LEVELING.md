# 体育场跑道平整修正 · 2026-09-24

两条跑道原来作为闭合 LineString 被地形平台处理遗漏，跑道和分道线仍贴在旧5米网格上，实际起伏分别达10.8215米和6.4507米。现把完整跑道及内场作为同一平面处理，并保留前版道路修正。

## 最新成果

- [可编辑 Blender 场景](CUHK_sports_leveled.blend)
- [校园总览](CUHK_sports_leveled_preview.png) · [建筑标签版](CUHK_sports_leveled_labeled.png)
- [第一处体育场近景](stadium_955764574_after.png) · [第二处体育场近景](stadium_955764585_after.png)
- [修正前后对照](sports_leveling_comparison.png)

## 修改与验证

两处运动面采用官方DTM区域中位值约5.334米、23.603米作为示意场坪标高；两条跑道、3个足球场及6个篮球场共11个表面的实际顶点高差均为0。分道线、球场标线位于面上2厘米，草坪条纹位于面上1厘米，球门和球网脚落在场地面。周边地形以10米过渡带接回原地形。

第一处体育场的旧内场轮廓与跑道平面范围重叠，内场及全部标线、球门布局绕场地中心统一收拢6.69%，修正后与跑道无重叠并保留至少30厘米余边；第二处内场平面尺寸未变。完整跑道平面轮廓与宽度保留。

北端弯道旁 Philosophy Path 原先与跑道重叠，局部向外平滑移动，最大位移3.85米，保留原高程、路径宽度及三处共享路口。修正后路面到跑道最短间隔1.2002米；路板底面同步，地形也随新位置整坡。

全量实际道路网格检查：1,602段道路、8,800,073个采样点，其中7,836点位于裁切地形之外。地形范围内穿地采样为0，翻折候选为0，最小路面离地余量0.2115米；1,747个共享节点连接保持完整。最后一次内场缩放未改动道路或地形。

[运动场实际网格检查](sports_actual_mesh_audit.json) · [道路检查](sports_road_surface_audit.json) · [场坪地形参数](sports_platforms.json) · [人行道局部调整](sports_path_adjustment.json) · [内场布局调整](sports_infield_fit.json)

这里的标高、布局收拢及局部道路位置是为协调参考数据而作的建模调整，不代表已测量的施工设计。原官方DTM、前版道路模型及修正前渲染均保留。

## 复现

以 `CUHK_roads_graded.blend` 为输入，先运行 `prepare_sports_platforms.py`、`prepare_sports_path_adjustment.py`，再次运行 `prepare_sports_platforms.py` 使地形采用调整后的路径，再运行 `prepare_sports_infield_fit.py`。随后在 Blender 中运行 `level_sports_facilities.py`、`audit_sports_candidate.py`、`render_sports_leveling.py`。运动面和细节共用统一场地标高，避免再次按地形逐点贴合。
