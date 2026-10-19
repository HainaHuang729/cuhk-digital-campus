# CUHK 照片参考重建 · 2026-09-10

最新模型：`CUHK_photo_rebuilt.blend`。这是 Blender / Cycles 输出，UE5 安装与导入已按用户要求暂停。

151 处已有名称全部搜索。模型中 136 处按照片更新外观，2 处按校方设计效果图近似建模；另有 13 处因缺图、仅有室内/场地图或身份无法核实，保留原示意体量。照片含单视角、组合远景及历史照片，不是全部当前实景测绘。

## 交付

- `CUHK_photo_rebuilt.blend`：含地形、平滑道路、建筑、材质及楼名，默认相机为核心校园鸟瞰。
- `CUHK_photo_rebuilt_preview.png`：3600 × 2700 无标签主图。
- `CUHK_photo_rebuilt_labeled.png`：3600 × 2700 带楼名主图。
- `CUHK_photo_rebuilt_plan.png`：4000 × 4400 全校园带楼名俯视。
- `CUHK_landmarks_gallery.png` 与 `landmark_previews/`：六栋重点建筑近景。
- `photo_reference_manifest.json`、`landmark_photo_references.json`：逐栋来源链接、图片缓存路径、实际视觉审查范围、外观描述。
- `photo_rebuild_report.json`：逐栋已实施外观类型和未核实清单。

## 本轮改动

替换有照片依据建筑原先统一的窗格及随机屋顶配色，重做条带窗、深竖肋、遮阳板、阳台、彩色板、局部坡屋顶与外墙材料。图书馆、邵逸夫堂、科学馆礼堂、李兆基建筑学大楼、康本国际学术园、罗桂祥阁六栋另行重做主要体量；狮子亭改为红柱、绿色攒尖顶。建筑学大楼等基础向下接到现有显示地形，旧通用细节叠加已移除。

原始建筑和细节保留在源文件/隐藏对象中；新版位于 `11 Photo reference architecture`。照片用于外观观察，不是贴在方盒上的整楼照片纹理。素材无需联网即可渲染，材质与中文标签字体保存在 blend 中。

## 精度与使用

这是依据照片修正的校园概念模型。OSM 平面位置和原有地形仍是定位基础；窗列间距、背面、未拍到的屋顶和精确高度未测绘。图书馆约 19m、罗桂祥阁约 18m、狮子亭约 4.9m 为明确估算。陈震夏宿舍校方文字为十层，本模型按 3.3m/层估高。组合照片中的宿舍只使用共有外观特征，不能据此认定每一面相同。

楼名取自原 OSM 标签，205 处校园建筑中 151 有名称、54 使用无名称占位符。标签是针对相机布置的可编辑三维文字；切换相机时需重新调用 `building_labels.apply_building_labels(camera, mode)`。关闭 `10 Building labels / OSM names` 的渲染即可看无标签场景。

地形与道路延续上一版的显示整平；原始 DTM 仍在 `terrain.npz`。源地形标称精度 ±5m，本模型不用于施工或测绘。

## 主要来源

- [中大官方校园地图](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html)
- [中大校园发展处项目照片](https://www.cdo.cuhk.edu.hk/projects/)
- [地政总署 5m DTM](https://data.gov.hk/en-data/dataset/hk-landsd-openmap-5m-grid-dtm)
- [OpenStreetMap contributors，ODbL](https://www.openstreetmap.org/copyright)

UE5：Epic Launcher 已安装至 E:/Epic Games，引擎尚未下载、未导入或渲染。`ue5/` 内脚本为待用交接文件。

## 逐栋重建记录

| 建筑 | 本轮状态 | 可见外观类型 | 参考 |
|---|---|---|---|
| 邵逸夫夫人樓 | 照片近似外观 | fins_and_bands | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H24) |
| 中國文化研究所 | 照片近似外观 | minimal_stone | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H4) |
| 湯若望宿舍 | 照片近似外观 | deep_vertical_bays | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U5) |
| 羅桂祥綜合生物醫學大樓 | 照片近似外观 | glass_front_and_ribbon_sides | [来源](https://www.cdo.cuhk.edu.hk/portfolio/lo-kwee-seong-integrated-biomedical-sciences-building/) |
| 鄭棟材樓 | 照片近似外观 | vertical_fins | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U3) |
| 碧秋樓 | 照片近似外观 | frame_grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H7) |
| 祖堯堂 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H2a) |
| 兆龍樓 | 照片近似外观 | frame_grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H6) |
| 五旬節會樓高座 | 照片近似外观 | repeated_hoods | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C34a) |
| 五旬節會樓低座 | 照片近似外观 | repeated_hoods | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C34b) |
| 邵逸夫堂 | 照片近似外观 | auditorium_canopy | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H9) |
| 逸夫科學大樓 | 照片近似外观 | colorful_glass_fins | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H34) |
| 知行樓 | 照片近似外观 | residence_bands | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N5) |
| 樂群館 - 梁雄姬樓 | 照片近似外观 | cylinder_and_portico | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N4) |
| 誠明館 | 照片近似外观 | projecting_roof_boxes | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N1) |
| 人文館 | 照片近似外观 | horizontal_bands | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N2) |
| 會友樓 | 照片近似外观 | residence_tile_cap | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N6) |
| 錢穆圖書館 | 照片近似外观 | library_central_box | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N3) |
| 紫霞樓 | 照片近似外观 | hoods_and_vertical_glass | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N9) |
| 志文樓 | 照片近似外观 | courtyard_residence | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N8) |
| 田家炳樓 | 照片近似外观 | tower_ribbon_windows | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H3a) |
| 高錕樓 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html) |
| 科學館東座 | 照片近似外观 | science_grid_arch | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H10a) |
| 李卓敏基本醫學大樓 | 照片近似外观 | grid_with_base_arches | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H11) |
| 大學圖書館 | 照片近似外观 | library_vertical_slits | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H3) |
| 科學館 | 照片近似外观 | faceted_cantilever | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H10) |
| 馬臨樓 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html) |
| 蒙民偉樓 | 照片近似外观 | yellow_cylinder_glass | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H30) |
| 嶺南體育館 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C6) |
| 方潤華堂 | 照片近似外观 | low_hall_clerestory | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C13) |
| 研究生宿舍第三座 | 照片近似外观 | balconies_stone_end | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C30) |
| 方樹泉樓 | 照片近似外观 | pink_vertical_window_frames | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C14) |
| 大學體育中心 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H21) |
| 文質堂 | 照片近似外观 | pastel_residence | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C24) |
| 明華堂 | 照片近似外观 | pink_grid_curved | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C21) |
| 應林堂 | 照片近似外观 | pink_grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C22) |
| 何善衡夫人宿舍 | 照片近似外观 | blue_core_residence | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C23) |
| 華連堂 | 照片近似外观 | brick_infill_grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C20) |
| 崇基學院教職員宿舍S座 | 照片近似外观 | yellow_base_stone | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C25) |
| 牟路思怡圖書館 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C11) |
| 利樹培堂 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C32) |
| 李冠春堂 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html) |
| 李慧珍樓 | 照片近似外观 | vertical_fins | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C3) |
| 利黃瑤璧樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C1) |
| 崇基學院行政樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C2) |
| 何添樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C8) |
| 崇基學院教職員聯誼會 | 照片近似外观 | curtain_wall | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C10) |
| 崇基學院禮拜堂 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C4) |
| 許讓成樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C3a) |
| 汾陽體育館 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H22) |
| 大學保健醫療中心 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H16) |
| 國際生舍堂三座 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=IH3) |
| 大學賓館 (曙光樓) | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H17b) |
| 雅禮賓館 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H17) |
| 昆棟樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H17a) |
| 芝苑 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H20a) |
| 職工宿舍第三座 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html) |
| 職工宿舍第二座 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H19) |
| 大學健身室 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H21) |
| 伯利衡宿舍 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U6) |
| 曾肇添樓 | 照片近似外观 | vertical_fins | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U1) |
| 陳震夏宿舍 | 照片近似外观 | white_louvres_zigzag_stair | [来源](https://www.uc.cuhk.edu.hk/student-hostels/chan-chun-ha-hostel/) |
| 胡忠多媒體圖書館 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U2) |
| 張祝珊師生康樂大樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U4) |
| 恒生樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U8) |
| 國際生舍堂一座 | 照片近似外观 | multicolor_balcony_soffits | [来源](https://www.cdo.cuhk.edu.hk/portfolio/renovation-works-to-international-house-1-2/) |
| 聯合苑 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=U7) |
| 研究生宿舍五座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=PGH5) |
| 研究生宿舍六座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=PGH6) |
| 研究生宿舍四座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=PGH4) |
| 國際生舍堂二座 | 照片近似外观 | multicolor_balcony_soffits | [来源](https://www.cdo.cuhk.edu.hk/portfolio/renovation-works-to-international-house-1-2/) |
| 第十三苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R13) |
| 第十五苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R15) |
| 第十二苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R12) |
| 第十苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R10) |
| 第十一苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R11) |
| 第十七苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R17) |
| 第十六苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R16) |
| 馮景禧樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H27) |
| 梁銶琚樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H28) |
| 第十四苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R14) |
| 范克廉樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H1) |
| 中文大學總部‵A‵變電站 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html) |
| 富爾敦樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H29) |
| 崇基教職員宿舍C座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C17) |
| 教研樓一座 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H33) |
| 崇基教職員宿舍B座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C16) |
| 蒙民偉工程學大樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H32) |
| 神學樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C5) |
| 崇基教職員宿舍A座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C15) |
| 何善衡工程學大樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H25) |
| 保安交通中心 | 照片近似外观 | blank | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H26) |
| 文林堂 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C31) |
| 三苑 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=R3) |
| 教研樓二座 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=E2) |
| 逸仙樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S6) |
| 第二學生宿舍（低座） | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S8) |
| 文瀾堂 | 照片近似外观 | blank | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S3) |
| 逸夫書院大講堂 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S5) |
| 國楙樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S1) |
| 衛星遙感地面接收站 | 照片近似外观 | blank | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H40) |
| 霍英東遙感科學館 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H40a) |
| 上海總會科研技術中心 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=E5) |
| 王福元樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C3b) |
| 信和樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C3d) |
| 陳國本樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C3c) |
| 何添堂 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=SH1) |
| 利國偉堂 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=SH2) |
| 大學行政樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H2) |
| 學思樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=N7) |
| 鄭裕彤樓 | 照片近似外观 | vertical_fins | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=E8) |
| 潤昌堂 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H8) |
| 李達三樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H23) |
| 李兆基樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H23a) |
| 李達三葉耀珍伉儷樓 | 照片近似外观 | curtain_wall | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H3b) |
| 格林伯格樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=MC1) |
| 敬文書院 | 照片近似外观 | charcoal_white_oversized_frames | [来源](https://www.cdo.cuhk.edu.hk/portfolio/c-w-chu-college/) |
| 和聲書院北座 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=WS2) |
| 伍宜孫書院 | 照片近似外观 | brown_perimeter_white_window_boxes | [来源](https://www.cdo.cuhk.edu.hk/portfolio/wu-yee-sun-college/) |
| 顧鐵華費肇芬伉儷樓 | 照片近似外观 | blank | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=WS1) |
| 李兆基建築學大樓 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C39c) |
| 康本國際學術園 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C39a) |
| 伍何曼原樓 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C39b) |
| 容啟東校長紀念樓 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C5a) |
| 龐萬倫學生中心 | 照片近似外观 | tan_infill_glass_courtyard | [来源](https://www.cdo.cuhk.edu.hk/portfolio/pommerenke-student-centre/) |
| 危險品貯存庫 | 外观未核实，保留示意 | — | [来源](https://www.cdo.cuhk.edu.hk/portfolio/construction-of-new-dg-stores-for-compressed-gases-on-campus/) |
| 晨興書院 | 照片近似外观 | white_frames_terracotta_ends | [来源](https://www.cdo.cuhk.edu.hk/portfolio/morningside-college/) |
| 香港生物科技研究院 | 照片近似外观 | curtain_wall | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=E1) |
| 香港中文大學海洋科學研究中心 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=E3) |
| 陳震夏館 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H15) |
| 何東夫人堂 | 照片近似外观 | grid | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H12) |
| 營修樓偏樓 | 照片近似外观 | blank | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H15a) |
| 如日坊 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html) |
| 雅群樓 | 照片近似外观 | balcony | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S4) |
| 禤永明樓 | 照片近似外观 | curtain_wall | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=S4a) |
| 香港中文大學賽馬會研究生宿舍二座 | 照片近似外观 | charcoal_hoods_blue_glass_boxes | [来源](https://www.cdo.cuhk.edu.hk/portfolio/jockey-club-postgraduate-halls-2-3/) |
| 香港中文大學賽馬會研究生宿舍三座 | 照片近似外观 | charcoal_hoods_blue_glass_boxes | [来源](https://www.cdo.cuhk.edu.hk/portfolio/jockey-club-postgraduate-halls-2-3/) |
| 蘭苑 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C9) |
| 賽馬會研究生宿舍一座 | 照片近似外观 | ribbon | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=PGH1) |
| 九龍中央獅子亭 | 照片近似外观 | red_column_green_pavilion | [来源](https://www.ccc.cuhk.edu.hk/en/content.php?wid=1749) |
| 物業管理處 | 外观未核实，保留示意 | — | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H46) |
| 眾志堂 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=C12) |
| 龔約翰學生中心 | 照片近似外观 | perforated_core_glass_portal | [来源](https://www.cdo.cuhk.edu.hk/portfolio/chung-chi-student-development-complex/) |
| 梁鳳儀樓 | 照片近似外观 | perforated_core_glass_portal | [来源](https://www.cdo.cuhk.edu.hk/portfolio/chung-chi-student-development-complex/) |
| 梅雲堂 | 照片近似外观 | white_slit_blocks | [来源](https://www.cdo.cuhk.edu.hk/portfolio/student-hostel-at-new-asia-college/) |
| 綜合科研實驗大樓（第2座） | 校方设计图近似 | white_portal_louvred_lab | [来源](https://www.cdo.cuhk.edu.hk/portfolio/centralised-general-research-laboratory-complex-block-2/) |
| 蔡繼有宿舍 | 照片近似外观 | white_courtyard_grid | [来源](https://www.cdo.cuhk.edu.hk/portfolio/student-hostel-at-united-college/) |
| 教學科研綜合大樓 | 校方设计图近似 | rounded_ribbon_v_pilotis | [来源](https://www.cdo.cuhk.edu.hk/portfolio/teaching-research-complex-in-area-39/) |
| 東翼 | 照片近似外观 | curtain_wall | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H4b) |
| 西翼 | 照片近似外观 | mixed | [来源](https://www.cuhk.edu.hk/english/campus/cuhk-campus-map.html?buildingcode=H4a) |
| 羅桂祥閣 | 照片近似外观 | cantilevered_concrete_museum | [来源](https://www.cdo.cuhk.edu.hk/portfolio/art-museum-of-the-chinese-university-of-hong-kong-lo-kwee-seong-pavilion/) |
