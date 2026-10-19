# 未圆湖植物与生态样板资料说明

资料核对日期：2026-09-28。此日期代表核对公开网页，**不代表现场调查日期**。

本轮交付 8 个植物观察区域和 5 个生态解说点，全部为 `confidence: approximate`、`locationType: area`。没有把随机树实例命名为某个物种，也没有导入或声称获得全校精确树木普查。

## 来源及证据范围

| 来源 | 本次使用 | 不支持的判断 |
| --- | --- | --- |
| [崇基学院：校湖](https://www.ccc.cuhk.edu.hk/tc/content.php?wid=401) | 未圆湖植物名单、无忧树相对位置、哲径及湖区历史 | 逐株经纬度、现时存活情况、树高 |
| [崇基校园通讯：崇基春季花卉，2023-03-20](https://www.ccc.cuhk.edu.hk/tc/publication_detail.php?id=109) | 六种植物的名称及形态，鸡蛋花位于湖西端 | 测量坐标、当前花期和每一棵树的身份 |
| [中大气候变化博物馆：体验城市生物多样性@未圆湖，2022](https://mocc.cuhk.edu.hk/zh-tw/news/2022/1079-experiencing-urban-biodiversity) | 人工生境、草地/树冠/池塘与观察活动的教育依据 | 当前鸟种、鸟数、水质或实时监测 |
| [香港政府绿化：樟](https://www.greening.gov.hk/en/community-outreach/qrcode-tree-labels/index_id_12.html) | 樟树英文名、学名及基本冠形 | 中大湖畔的具体树位 |
| [康文署：落羽杉](https://www.lcsd.gov.hk/tc/green/education/greeningknowledge/plantphoto/tree_passage/taxodium_distichum.html) | 落羽杉英文名、学名 | 中大湖畔的具体树位 |
| [CUHK Campus 100 Plants，2023](https://socialimpact.cuhk.edu.hk/social-impact-events/cuhk-campus-100-plants/) | 作为校园植物探索项目的背景依据 | 此公告没有本轮可核实的逐株坐标数据，未据此捏造点位 |

六个采用的来源均于本轮成功取得 HTTP 200。`source_receipts.json` 记录获取 UTC 时间、最终地址、内容大小与 SHA-256。原始网页保存在 `C:/Users/Amadeus/.agent-reach/cuhk/ecology/`，不随网页发布。只发布简短改写的说明与来源链接，不复制官方照片。

额外查到 SRSDO 的落羽松资料，搜索索引仍能读取，其直接地址本轮返回 404；因此前端使用仍可读取的崇基学院湖区名单和康文署分类资料。胡秀英植物标本馆樟树页在本机直连出现证书链错误，未关闭证书校验；改用引用该标本馆的政府樟树资料页。

## 八个植物区域

| 中文名 | 学名（沿用来源） | 区域精度 | visualType |
| --- | --- | --- | --- |
| 樟树 | Cinnamomum camphora | 湖岸区域 | tall_tree |
| 落羽松／落羽杉 | Taxodium distichum | 湖岸区域 | slender |
| 鸡蛋花 | Plumeria rubra | 官方文章明确湖西端，仍非树干坐标 | spreading |
| 串钱柳 | Callistemon viminalis | 湖岸区域 | medium_tree |
| 无忧树 | Saraca dives | 文章记载曲桥北端；未核对到测绘坐标 | medium_tree |
| 山茶 | Camellia japonica | 湖岸区域 | shrub |
| 软枝黄蝉 | Allamanda cathartica | 湖岸区域 | shrub |
| 大红花 | Hibiscus rosa-sinensis | 文献记载未圆湖及何草一带，本样板仅湖区 | shrub |

无忧树的学名采用崇基学院 2023 年文章的 `Saraca dives`，不把同属其它物种或其它地点的同名树强行合并；现场身份与现行分类学复核仍待补充。所有树高、冠幅与花色表现都只是共享树型的示意，不是该株的实测值。英文普通名用于阅读，判别应参考学名和来源。

五种树型分别表达高大宽冠、中型树、低灌木、展开冠和细高冠。记录的 `visualType` 是形态映射，不是把一个随机树实例升级成已识别单株。区域周边的树木仍为轻量环境资产；没有新增全校物种归属。

## 五个生态点

1. 城市里的生境拼图：解释草地、树冠、池塘的相邻关系。
2. 水陆交界：邀请观察湖面、湖岸和遮荫，未加入水质数值。
3. 停下来，听树冠：观察提示，不指定鸟种，不声称存在当天观测记录。
4. 为什么叫未圆湖：湖区与名称的历史解释。
5. 沿哲径慢行：环湖观察的入口；不是导航、无障碍或当前开放状况数据。

鸟的动画活动范围只是依据湖区空间组织的视觉设计，与生物追踪、真实群体行为及实时出现记录无关。卡片统一附有「此为资料支持的生态解说点，不是实时监测或逐株树木普查」。

## 坐标与区域方法

湖面使用主模型现有 `artifacts/cuhk/geodata.json` 的 OSM 水体 `33411938`。该多边形的本地坐标已由原项目的地理转换流程生成，保留原多边形而非重新画一片湖。对应 Three.js 水平边界为：

- X：148.370 至 307.029 米；Z：376.337 至 539.166 米。
- 样板开发边界：X 130–325，Z 355–555 米，覆盖湖岸及紧邻步道。
- 世界坐标单位：米；水平原点为 HK1980 Grid / EPSG:2326 的 E 839400，N 831150。
- 转换：`Three = [E - 839400, H, -(N - 831150)]`。没有缩放、额外旋转或人工地理平移。
- 湖区解释中心 `[232, 6.6, 445]` 是模型展示中心；6.6 米是场景高度近似，**不是校方测量水位**。

生态资料仅提供区域文字定位，因此植物的 `approximateLocation` 一般指向整个湖岸，展示半径 125 米；鸡蛋花指向湖西端，展示半径 40 米。半径用于画面表达范围，不是定位误差统计或调查边界。`position` 则是防止标签重叠的**显示锚点**；不同锚点不表示树木只分布于该点。标签高度来自已有 20 米高度场邻近四格的最大值加 6 米，目的是可读，不代表树冠高度。

本轮没有植物资料的 WGS84 实测坐标，所以没有反推假的经纬度。若后续获得可靠 WGS84 记录，应按原项目 `pyproj.Transformer.from_crs(4326, 2326, always_xy=True)` 转换经纬度到 E/N，再用上述固定转换；高程必须单独确认 HKPD 与椭球高差异。

## 数据字段与维护

数据文件：`cuhk-campus-web/public/campus/ecology.json`。`plants` 和 `points` 共用 `id/source/verifiedAt/confidence/locationType/position/approximateLocation/notes/notice`。植物另有中英文名、学名、category、habitat、visualType；生态点另有 type、title、subtitle、description。

- `source`：数组，每项含 title、url、scope、id、verifiedAt。来源支持什么写在 scope，不能用分类资料证明校园位置。
- `verifiedAt`：网页资料核对日。需要新增 `observedAt` 才能表达未来实地观察日，两者不能互换。
- `confidence: exact`：仅在有可复核的逐株／设施坐标和实地依据后使用。本数据没有 exact。
- `confidence: approximate`：来源明确提到地点或区域，但没有精确坐标。本样板全部属于此类。
- `confidence: inferred`：由模型或生境推断，不能拿来证明物种出现。本样板没有推断物种记录。

更新经过核实的条目后，执行 `python -X utf8 artifacts/cuhk/ecology/build_ecology.py`。生成器会检查 8+5 条目的唯一 ID、有限坐标、样板范围、来源链接、区域可信度和全部五种树型覆盖。无需联网运行，未增加依赖。

## 尚未完成

逐株坐标、树牌对照、树高冠幅、现时存活和移植状态、统一植物分类学复核、当前花期，以及实测鸟类记录均未取得。样板之外的树木仍无物种认定。本轮的截图与画面检查由网页集成验证记录负责，不能替代实地生态核查。
