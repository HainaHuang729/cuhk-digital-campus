# 道路整坡前后实际渲染检查

最终检查更新：2026-09-24。仅重渲染整坡版的两处 `after`，保留原 `before` 和相机。陈震夏宿舍 `(-256,240)` 附近此前遮住低层窗格的三角土丘已消失，正面最低层窗带恢复可见；楼体悬高和三岔路口重叠暗斑明显改善。桥头路面保持连续，两个端帽未再出现放射状暗纹。

两处指定镜头的这些问题已通过目视复核。宿舍右后方上层台地仍为较陡的示意边坡；本检查不证明全校园所有建筑及地形均无相交，也不将示意边坡解释为实测挡土结构。

对照来源：`CUHK_connected_roads.blend`（上一版）和 `CUHK_roads_graded.blend`（整坡版）。两份原模型均只读加载；渲染脚本不保存任何 `.blend`。

| 检查部位 | 文件前缀 | 镜头目标 | 相机相对目标偏移 | 正交宽度 |
|---|---|---|---|---|
| OSM 2231906278 桥头 | `road_grading_bridgehead_` | `(305.427638651,205.126932662,138)` | `(-10,75,58)` | 78 m |
| 陈震夏宿舍旁深切及路口 | `road_grading_hostel_` | `(-263,244,139)` | `(-100,-25,72)` | 105 m |

每处输出 `before.png` / `after.png`（各1600×1200）与 `comparison.png`（原像素拼接）。另有两处合并检查板 `road_grading_comparison.png`。`preview` 文件只用于选镜头，不用于最终拼图。

`road_grading_hostel_base_crop.png` 是最新宿舍检查图中 `(710,740)–(1160,1040)` 像素区域的2倍放大，便于核对低层窗带；仅裁切缩放，没有补画。正式对照拼图保持原始渲染像素，拼接脚本逐像素验证。

统一设置：Cycles、32 samples、降噪、AgX、固定相机及同一太阳/环境光。两条桥头路使用同一琥珀色检查材质，其他道路使用统一沥青或步道材质；地形与建筑保留，标签和植被统一隐藏。渲染几何来自实际 Blender 文件，不进行生成式补画、擦除穿模或修饰路面。

这些检查图用于发现可见穿模、道路折面和地形切口；不能替代整体几何检查，也不代表示意模型道路纵坡、桥梁或建筑基础已经实测验证。

复现（在本目录下）：

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python './render_road_grading_check.py'
& 'C:/Users/Amadeus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' './compose_road_grading_check.py'
```

可追加 `-- --only before` / `-- --only after` 或 `-- --view bridgehead` / `-- --view hostel` 单独重跑。
