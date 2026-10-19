# CUHK · Interactive Digital Campus

香港中文大学的交互式 Three.js 数字校园。沿用 `CUHK_shaw_science_corrected.blend` 的建筑与地形，加入连续昼夜、分区细节加载、校园活动和建筑故事；原始 Blender 文件保持不变。

## 启动与打包

需要 Node.js 22.12 或更新版本。在本目录运行：

```powershell
npm ci
npm run dev
```

打开 [本机校园](http://127.0.0.1:5178)，等待载入后点击 **ENTER**。也可双击 `启动校园网页.cmd`，保持启动窗口运行。

`npm run build` 生成 `dist`；停止开发服务后，可用 `npm run preview` 在同一地址预览。部署时将 `dist` 的全部内容放在静态网站根目录；资源路径从 `/` 开始。浏览器需支持 WebGL 2 并启用硬件加速。

## 探索校园

- **镜头**：拖动旋转、滚轮缩放、右键平移；触屏单指旋转、双指缩放与平移。点击楼体或名称查看详情并飞向建筑，双击楼体或点击 **Focus** 靠近；详情中的 **Explore** 收起卡片继续观察。
- **Explore**：山海全景、中央校园、山上书院、沿海漫游；可切换名称和全屏。右侧指南针切换正北俯视，`＋` / `−` 调整距离，左上角 CUHK 返回总览。
- **Places**：支持简体、繁体和英文搜索；按 `/` 进入搜索，Enter 定位首个结果。
- **食堂和公交站**：默认标出17处食堂／饭堂和25处校巴站，左上角可分别开关；大楼名称默认隐藏，可在 Explore 中重新打开。Places 提供食堂／公交站／建筑分类，点击地点可飞向位置并查看来源。点位来自校方资料，临时迁站请以地点卡片链接的交通通告为准。详细覆盖范围见[地点来源说明](../artifacts/cuhk/audits/digital_campus/AMENITY_SOURCES.md)，这不是所有实时营运站点的完整清单。
- **Time**：拖动 0–24 时滑杆、点击时间刻度或播放一天，连续改变太阳、天空、雾、曝光、窗户和路灯。初始为 16:30；时间与光照为场景表达，不是实时天气或天文模拟。
- **Stories**：目前提供逸夫科学大楼 2007 年建筑获奖、2011 年命名两段故事，附校方照片和来源链接。其他建筑未补充资料时，Story 按钮不可用。
- **Ecology**：按需打开未圆湖样板，查看植物与生态区域标记、类别筛选及资料来源。首次进入自动飞向湖区；收起面板后仍可点击标记，“返回 Explore”退出。标记表示资料支持的观察区域，不是树干实测点，也不是实时监测。
- **Photo**：点击 Photo 或按 `C` 收起界面与名称，拖动构图后保存 PNG。图片仅包含三维画面；按 Esc 或“返回 Explore”退出摄影。
- **校园活动**：复用原树木模板与位置，加入树影微动、示意行人、车辆、自行车、飞鸟及路边小物；它们不是实时校园数据。系统尊重减少动态效果的浏览器设置。

按 Esc 可关闭探索面板、取消选择或停止自动环绕。

## 调试与画质

按 `P` 显示性能面板，按 `D` 打开调试面板，按 `B` 启停约 12 秒的环绕采样。调试项包括 Auto / High / Medium / Low 画质、太阳方向、曝光、雾、环境反射、LOD 距离、阴影、近景 AO、校园活动及植被。

展开 **逸夫科学大楼 · 几何校准**，可按需加载政府公开三维数据参考层，调透明度、显示建筑边界框并导出同镜头的模型／参考对照图。只载入本地预裁的小范围样板，不连接整片城市瓦片流。官方建筑高度存在约 2.8 米的垂直基准解释差异，工具提供两种明确标记的解释；这不是手调偏移，也不自动修改主模型。建筑轮廓、屋顶与高程不能等同于同精度、同年代的实测结果。

调试中的 **未圆湖局部视觉优化** 可即时恢复原始湖面、地形和植被，用于相同镜头前后比较。修改只作用于网页运行时，原始 Blender 和静态校园 GLB 保持不变。

本轮的来源、字段、坐标、几何差异、回退方式和实际前后截图见 [局部样板交付](../artifacts/cuhk/SAMPLE_DELIVERY.md)。

窄屏初始使用 Low，其他窗口初始使用 High；Auto 在持续低帧率时逐级降档。画质同时影响像素密度、阴影、近区建筑细节、植被和活动数量；轻度 AO 仅用于 High 的近景。

性能面板统计实际绘制帧、绘制次数、三角面、帧间隔及可用的内存信息。`assets` 是当前场景模型对应的压缩 GLB 载入量，`Geometry` 是几何缓冲数据估算，两者都不是 GPU 显存。实际表现取决于设备、视角和画质；验证记录见 [VERIFICATION.md](VERIFICATION.md)，升级前基线见 [DIGITAL_CAMPUS_AUDIT.md](DIGITAL_CAMPUS_AUDIT.md)。

## 模型与加载

369 个可识别楼体，其中校内 204 个，包含全部 151 个已命名建筑；原清单中 1 个无名隐藏对象未导出。校园范围约 2.4 × 2.4 公里，单位为米，坐标由 Blender `(x,y,z)` 转为 Three.js `(x,z,-y)`。建筑目录保留在 `public/model/buildings.json`。

当前 `public/campus/manifest.json` 管理 16 块地形、场地模型、常驻低细节建筑及 12 个建筑分区的中／高细节模型，共 **42 个 Meshopt GLB**。初始地形、场地与建筑包为 **24,059,236 字节、4,285,449 个三角面、594 个基础 primitive**，不包含另行载入的植被与校园活动。594 是完整基础模型的 primitive 数量，不是浏览器运行时的绘制次数。

近处或选中的分区按画质补充细节，最多同时载入两个细节文件；远离后恢复常驻轮廓并释放高细节资源。原道路和运动场几何保留，地形在道路、场地及逸夫科学大楼附近保留细节，其他区域降采样并缝合边界。1,374 棵原树木使用 8 个共享模板实例化，避免逐棵展开几何。

建筑继续保留原始逐面材质分区，包括玻璃、金属、遮阳板及屋顶。模型材质使用 PBR 参数，没有图像材质贴图，因此本次未应用 KTX2 或贴图合图；故事照片属于界面图片。Meshopt 解码器随 Three.js 打包；校园活动资源仍可使用本地 Draco 解码器，无需第三方解码 CDN。旧 `public/model` GLB 保留作对照。

## 模块结构

| 文件 | 职责 |
| --- | --- |
| `main.js`、`index.html`、`style.css` | 场景组装、渲染调度、页面结构与响应布局 |
| `src/core/CameraFlight.js` | 视角飞行、建筑聚焦与地形净空约束 |
| `src/systems/TimeOfDaySystem.js` | 连续昼夜、材质夜间发光与观察区域阴影 |
| `src/systems/StreamingSystem.js` | 分区 LOD、并发加载、替换与资源释放 |
| `src/systems/CampusLife.js` | 植被实例化、道路活动与场景小物 |
| `src/systems/BuildingInteraction.js` | 楼体拾取、悬停与选中高亮 |
| `src/systems/PostProcessingSystem.js` | High 近景 AO 与输出色彩处理 |
| `src/systems/QualitySystem.js`、`src/systems/PerformanceMonitor.js` | 画质降档与绘制指标采样 |
| `src/ui/`、`src/data/campusData.js`、`search.js` | 面板、名称、地点和故事配置、建筑搜索 |

## 导出与优化复现

网页依赖与离线资产工具分开安装。从本目录执行以下步骤；`blender` 需指向已安装的 Blender：

```powershell
blender --background --python ../artifacts/cuhk/export_digital_campus.py
npm ci --prefix ../artifacts/cuhk/tools/gltf
node ../artifacts/cuhk/tools/gltf/build_digital_campus.mjs
node ../artifacts/cuhk/tools/gltf/validate_digital_campus.mjs
```

这条流程重建并验证地形、场地和建筑资源。校园活动另由 `../artifacts/cuhk/export_campus_life.py` 导出。压缩选择、保护范围、详细复现步骤及机器可读报告见[资产与加载审计](../artifacts/cuhk/audits/digital_campus/ASSETS_AND_STREAMING.md)。`npm test` 运行项目自动检查；浏览器视觉与性能记录见上方验证文档。

## 来源与限制

地形来自香港政府 CEDD LiDAR 派生资料，部分缺测区沿用既有地形，显示模型按道路与场地局部修整。建筑、道路与名称来自 © OpenStreetMap contributors（[ODbL](https://www.openstreetmap.org/copyright)），部分外观参考校方照片。高度、外观与树冠包含估算或示意，不用于实测或导航。

**逸夫科学大楼高度修正**：根据中大官方六层建筑资料及本地 CEDD 0.5 米 DSM，主要屋面从 90.65 米校正至 111.6 米 HKPD，两端设备结构约 117.6 米 HKPD；五排彩色幕墙对应照片可见实验室楼层。网页显示约 36.9 米，为相对模型参考基底且含屋顶结构的高度，并非校方公布的实测总高。上坡背面地形局部恢复，所有道路顶面外围 3 米内地形保持不变。详细依据见[逸夫科学大楼修正说明](../artifacts/cuhk/SHAW_SCIENCE_CORRECTION.md)。
