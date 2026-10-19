# 道路连续性渲染检查

- `road_continuity_before.png`：原 `CUHK_photo_rebuilt.blend` 的实际 Blender 渲染。
- `road_continuity_after.png`：修复后 `CUHK_connected_roads.blend` 的实际 Blender 渲染。
- `road_continuity_comparison.png`：左右原图拼接，加说明栏；没有修图或生成式补画。

检查对象为 OSM 路段 **213510397** 和 **213510536** 的真实共享节点 **2231906278**，场景米制坐标 **X=305.427638651，Y=205.126932662**。旧路网审计记录该节点原中心线标高错位 **13.3878 m**，原显示路面错位 **13.3118 m**。数值属于现有模型，不能解释为实地路况。

两张图使用同一个固定北侧正交镜头：目标 `(305.427638651, 205.126932662, 138)`；相机 `(295.427638651, 280.126932662, 196)`；正交画幅宽 78 m。统一使用 Cycles、32 samples、降噪、1600×1200 像素、AgX、同一太阳方向与环境光。

两条检查路统一改为琥珀色以便辨认。建筑和地形保留，标签与植被一致隐藏。材质和隐藏操作只作用于渲染进程中的临时场景；脚本没有保存或覆盖任何 `.blend`。

这些图检查的是已有示意模型的道路表面连续性，不表示建筑细节、道路纵坡或地形精度已经得到实地测量验证。

复现：

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python './render_road_continuity_check.py'
& 'C:/Users/Amadeus/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' './compose_road_continuity_check.py'
```

渲染脚本支持 `-- --only before` 或 `-- --only after` 单独更新一侧，`-- --preview` 生成较低分辨率的选镜头预览。最终交付图不采用预览图。
