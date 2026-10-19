# Digital Campus — 基线与优先级

2026-09-26；在任何大规模更改之前读取原项目，并在原渲染中加入仅用于测量的帧计数。原页面、样式、入口代码备份在 `../artifacts/cuhk/audits/digital_campus/baseline/`。

| 检查 | 升级前 |
|---|---|
| 项目结构 | Vite；main.js 约21 KB集中渲染/交互，index.html、style.css、search.js，public/model与本地Draco解码器 |
| Three.js版本 | 0.185.1（锁文件）；Vite 8.0.13 |
| Renderer | WebGL2，sRGB，ACESFilmic，exposure 1.0，DPR上限1.7；静止时按需绘制 |
| 模型加载 | GLTFLoader + DRACOLoader，两个GLB依次全量加载；无区域卸载 |
| GLB | terrain 14,566,228 B；campus 20,076,888 B；总34,643,116 B |
| Triangle count | 地形5,269,222 + 校园2,343,302 = 7,612,524；建筑818,377，树472,656 |
| Draw calls | 完整颜色pass理论1,389；实测中央校园环绕约1,028（随视锥变化，阴影另计） |
| 贴图 | GLB内0 textures、0 images、0 UV；223校园材质+2地形材质，以PBR参数为主；运行时4个环境/阴影等纹理对象 |
| 灯光 | Hemisphere 1.35 + Directional 2.8 + RoomEnvironment PMREM；scene与material都乘.3，环境反射实际乘.09 |
| 阴影 | PCF 4096，范围140–1550m随镜头收紧，静态缓存；已存在正确思路，不必直接换CSM |
| FPS | 本机RTX 4090；CSS 1280×720、DPR1.5，即1920×1080渲染；中央校园环绕159.3 FPS，3秒窗p95 6.3ms；JS heap当次249.9 MB。静止时不以rAF空循环冒充绘制FPS |
| 模型尺寸 | 约2.4×2.4公里，米制；Blender(x,y,z)→Three(x,z,-y)。Shaw已校正，跑道已平整 |
| 最明显视觉问题 | 日/晚二态；大面积侧栏；静态环境；环境反射偏弱；没有轻度接触阴影与夜间照明 |
| 最严重性能问题 | 69%三角面来自地形；建筑1364次绘制；所有高细节一次载入，树从8共享模板展开，无LOD/streaming |

这是本机特定浏览器与显卡的基线，不是集显或手机的性能保证。

## High Priority

1. 保留正确色彩管理，修正环境强度叠乘；复用单太阳动态观察区阴影。
2. 时间系统独立模块，连续太阳/天空/雾/曝光/窗户/路灯，晨午夕夜实际验证。
3. 全屏入场与按需面板；统一CameraFlight、建筑配置、hover/点击/双击、搜索与信息。
4. 性能监测与可复现帧率数据；地形分块、低中高建筑资产、近区加载和远区释放。

## Medium Priority

1. High近景轻度GTAO，限制额外geometry pass成本，统一OutputPass色彩处理。
2. 将原1374棵树恢复为8模板实例化及近远LOD；少量真实道路上的示意行人、车、自行车、鸟。
3. 复用157路灯，少量柔和路面光斑；添加已确认缺少的长椅、垃圾桶、停放单车。
4. 手机起始Low，限制DPR/阴影/人物/LOD；持续低帧率后降档并有冷却。

## Low Priority / 条件触发

1. 数据驱动Stories示例与摄影模式，后续可扩充地点。
2. 当前没有PNG/JPG材质贴图，KTX2/atlas没有实际转换对象；未来引入真实PBR纹理时先合图并转KTX2，再加KTX2Loader。
3. CSM多级会增加大场景阴影pass；先保留观察区跟随阴影。天气/历史年代模型/室内/VR目前不展开。

资产审计与优化证据：`../artifacts/cuhk/audits/digital_campus/ASSETS_AND_STREAMING.md`；原始资源与可编辑Blender模型保留。
