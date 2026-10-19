"""Rebuild the small, source-grounded lake interpretation dataset; no tree survey implied."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PUBLIC = ROOT / 'cuhk-campus-web/public/campus'
VERIFIED = '2026-09-28'
# Presentation cameras use the saved terrain clearance grid and building bounds.
# These are elevated compositions, not surveyed visitor or plant coordinates.
LAKE_VIEWS = {
    'shoreline': {'label': '湖岸漫步', 'position': [178, 30, 456], 'target': [238, 8, 407]},
    'philosophy': {'label': '哲径望湖', 'position': [261, 28, 498], 'target': [283, 8, 434]},
}
PLANT_VIEWS = {
    'camphor': ([178, 30, 456], [238, 8, 407]),
    'bald-cypress': ([261, 29, 490], [298, 10, 499]),
    'frangipani': ([193, 30, 452], [154, 10, 417]),
    'bottlebrush': ([263, 30, 445], [303, 10, 424]),
    'saraca': ([245, 30, 424], [281, 10, 382]),
    'camellia': ([222, 29, 475], [189, 8, 443]),
    'allamanda': ([257, 29, 484], [294, 10, 460]),
    'hibiscus': ([246, 28, 510], [272, 9, 541]),
}
SOURCES = {
    'lake': {'title': '香港中文大学崇基学院：校湖', 'url': 'https://www.ccc.cuhk.edu.hk/tc/content.php?wid=401', 'scope': '湖区植物名单、文化与哲径；无树干坐标'},
    'spring': {'title': '崇基校园通讯：崇基春季花卉（2023-03-20）', 'url': 'https://www.ccc.cuhk.edu.hk/tc/publication_detail.php?id=109', 'scope': '湖畔植物名称、形态；鸡蛋花位于湖西端'},
    'mocc': {'title': '中大气候变化博物馆：体验城市生物多样性@未圆湖（2022）', 'url': 'https://mocc.cuhk.edu.hk/zh-tw/news/2022/1079-experiencing-urban-biodiversity', 'scope': '人工生境、草地、树冠、池塘与生态观察；非当前监测'},
    'camphor': {'title': '香港政府绿化：樟树资料', 'url': 'https://www.greening.gov.hk/en/community-outreach/qrcode-tree-labels/index_id_12.html', 'scope': '樟树学名、英文名及形态；非中大位置数据'},
    'cypress': {'title': '康乐及文化事务署：落羽杉植物图鉴', 'url': 'https://www.lcsd.gov.hk/tc/green/education/greeningknowledge/plantphoto/tree_passage/taxodium_distichum.html', 'scope': '落羽杉学名及英文名；非中大位置数据'},
    'hundred': {'title': 'CUHK Campus 100 Plants（2023）', 'url': 'https://socialimpact.cuhk.edu.hk/social-impact-events/cuhk-campus-100-plants/', 'scope': '项目背景；本轮未获取可核实的逐株坐标数据'},
}
for key, source in SOURCES.items():
    source.update(id=key, verifiedAt=VERIFIED)


def sources(*keys):
    return [SOURCES[key] for key in keys]


def build():
    terrain = json.loads((PUBLIC / 'heightfield.json').read_text(encoding='utf-8'))
    geo = json.loads((ROOT / 'artifacts/cuhk/geodata.json').read_text(encoding='utf-8'))
    lake = next(f for f in geo['features'] if f['id'] == 33411938)
    ring = [[round(x, 3), round(-north, 3)] for x, north in lake['geometry']['coordinates'][0]]

    def marker(x, z):
        col = max(0, min(terrain['cols'] - 2, math.floor((x - terrain['xmin']) / terrain['step'])))
        row = max(0, min(terrain['rows'] - 2, math.floor((z - terrain['zmin']) / terrain['step'])))
        height = max(terrain['heights'][r * terrain['cols'] + c]
                     for r in (row, row + 1) for c in (col, col + 1))
        return [x, round(height + 6, 3), z]

    area = {'name': '未圆湖湖岸观察区域', 'position': [232, 6.6, 445], 'radiusMeters': 125,
            'method': '依据现有湖面边界划定的解释区域；标记为排版锚点，不是树干中心或调查范围边界。'}
    notice = '此为资料支持的生态解说点，不是实时监测或逐株树木普查。'
    records = [
        ('camphor', '樟树', 'Camphor tree', 'Cinnamomum camphora', 'tree', 'tall_tree', 220, 366,
         '常绿乔木，冠形宽阔。崇基学院的湖区介绍明确列有樟树。', ('lake', 'camphor')),
        ('bald-cypress', '落羽松（落羽杉）', 'Bald cypress', 'Taxodium distichum', 'tree', 'slender', 303, 500,
         '湖边高大乔木之一，采用细高冠形作示意。名称与现存单株仍需现场核对。', ('lake', 'cypress')),
        ('frangipani', '鸡蛋花', 'Frangipani', 'Plumeria rubra', 'tree', 'spreading', 145, 420,
         '崇基校园通讯将鸡蛋花记于未圆湖西端；小乔木以展开冠形呈现。', ('spring',)),
        ('bottlebrush', '串钱柳', 'Weeping bottlebrush', 'Callistemon viminalis', 'tree', 'medium_tree', 310, 424,
         '湖畔小乔木，枝条柔软下垂，红色花序呈刷状。', ('spring', 'lake')),
        ('saraca', '无忧树', 'Saraca (Wu You tree)', 'Saraca dives', 'tree', 'medium_tree', 281, 380,
         '校方记载曲桥北端湖畔有无忧树，承载开放与包容的文化寓意。', ('lake', 'spring')),
        ('camellia', '山茶', 'Japanese camellia', 'Camellia japonica', 'shrub', 'shrub', 185, 445,
         '校园通讯记载湖畔常见山茶，崇基的山茶多呈灌木形态。', ('spring',)),
        ('allamanda', '软枝黄蝉', 'Golden trumpet', 'Allamanda cathartica', 'shrub', 'shrub', 299, 459,
         '湖区资料记载的常绿灌木，花为黄色漏斗状。', ('spring', 'lake')),
        ('hibiscus', '大红花', 'Chinese hibiscus', 'Hibiscus rosa-sinensis', 'shrub', 'shrub', 269, 548,
         '校园通讯记录其分布于未圆湖及何草一带；这里仅表示湖区可见。', ('spring',)),
    ]
    plants = []
    for ident, zh, en, latin, category, visual, x, z, description, refs in records:
        location = dict(area)
        if ident == 'frangipani':
            location.update(name='未圆湖西端观察区域', position=[164, 6.6, 415], radiusMeters=40,
                            method='校方文章仅明确湖西端；40米为展示区域半径，非定位误差或调查边界。')
        notes = '出处确认区域曾有此植物；无逐株坐标，未与现有随机树实例绑定。学名沿用所列来源。'
        if ident == 'saraca':
            notes += '曲桥北端的文字定位尚未与测绘坐标核对；Saraca dives 为2023年校方文章使用的名称，未作现场分类学复核。'
        camera, target = PLANT_VIEWS[ident]
        plants.append({'id': 'plant-' + ident, 'type': 'plant', 'nameZh': zh, 'nameEn': en,
                       'scientificName': latin, 'category': category,
                       'habitat': 'aquatic_edge' if ident == 'bald-cypress' else 'lakeside',
                       'description': description, 'source': sources(*refs), 'verifiedAt': VERIFIED,
                       'confidence': 'approximate', 'locationType': 'area', 'position': marker(x, z),
                       'approximateLocation': location, 'notes': notes, 'visualType': visual, 'notice': notice,
                       'presentation': {'view': {'position': camera, 'target': target}}})
    points = []
    entries = [
        ('urban-habitat', 'habitat', '城市里的生境拼图', '草地 · 树冠 · 池塘', 225, 403,
         '未圆湖的不同景观共同提供生物栖息空间。这一小片人工环境，是中大城市生物多样性体验活动的观察场所。', ('mocc',)),
        ('water-edge', 'habitat', '水陆交界', '湖面与湖岸', 285, 478,
         '湖岸植物与池塘构成相邻生境。此点邀请观察水面、岸边和遮荫差异，不代表水质、物种数量或当日生态状态。', ('mocc', 'lake')),
        ('canopy', 'observation', '停下来，听树冠', '树冠与草地观察区', 190, 379,
         '树冠与草地为动物和昆虫提供食物与庇护。这里可尝试安静聆听与观察；动画鸟仅为氛围示意，未指认鸟种或当天记录。', ('mocc',)),
        ('lake-story', 'story', '为什么叫未圆湖', '从荷花池到未圆湖', 155, 436,
         '湖区由早年的农田与水道逐渐改建。名字寄托持续向完善努力的理念，回应崇基学院的校训。', ('lake',)),
        ('philosophy-path', 'observation', '沿哲径慢行', '环湖观察路线', 262, 443,
         '校方把环湖小径称为哲径。这个区域标记提供观察起点，可留意植被层次与水岸关系；不提供无障碍或现场通行保证。', ('lake', 'mocc')),
    ]
    for ident, kind, title, subtitle, x, z, description, refs in entries:
        points.append({'id': 'ecology-' + ident, 'type': kind, 'title': title, 'subtitle': subtitle,
                       'description': description, 'source': sources(*refs), 'verifiedAt': VERIFIED,
                       'confidence': 'approximate', 'locationType': 'area', 'position': marker(x, z),
                       'approximateLocation': dict(area), 'notes': '解释性观察锚点，不代表实地调查站或精确设施位置。', 'notice': notice,
                       'presentation': {'view': LAKE_VIEWS['philosophy' if x > 250 else 'shoreline']}})
    data = {
        'version': 1, 'verifiedAt': VERIFIED, 'verificationMeaning': '网页资料核对日期，不是实地观察日期。',
        'notice': notice,
        'confidenceDefinitions': {'exact': '有可复核的逐株或设施坐标及现场依据；本样板无此类记录。',
                                  'approximate': '资料明确提及地点或区域，展示为近似观察区域。',
                                  'inferred': '仅由生境或模型推断，不能当作物种出现记录；本样板未用于物种。'},
        'sample': {'id': 'lake-ad-excellentiam', 'name': '未圆湖生态样板', 'center': [232, 6.6, 445],
                   'bounds': {'min': [130, 0, 355], 'max': [325, 45, 555]},
                   'lakeBoundaryXZ': ring, 'boundarySource': 'artifacts/cuhk/geodata.json · OSM water 33411938',
                   'view': {'position': [420, 225, 715], 'target': [232, 8, 445]},
                   'presentation': {'views': LAKE_VIEWS,
                                    'meaning': '湖岸附近的抬高观察构图；镜头位置不代表实地观测站、精确植物位置或第一人称步行路线。'},
                   'birdArea': {'center': [237, 27, 422], 'radiusX': 60, 'radiusZ': 28, 'heightRange': [19, 38],
                                'meaning': '限制氛围动画的局部活动区域；非鸟种分布或监测记录。'},
                   'coordinateSystem': {'horizontal': 'HK1980 / Hong Kong 1980 Grid (EPSG:2326)',
                                        'vertical': '场景沿用 HKPD；生态锚点高度来自现有地形，非实测水位。',
                                        'origin': [839400, 831150], 'units': 'metres',
                                        'toThree': '[easting - 839400, height, -(northing - 831150)]',
                                        'markerHeight': '现有20米高度场相邻四格最大值+6米；仅用于可读性。'},
                   'scope': '湖面、湖岸及紧邻步道的局部解释样板；范围为开发边界，不是官方保护区边界。'},
        'visualTypes': {
            'tall_tree': {'label': '高大乔木', 'description': '高干与宽厚树冠，示意樟树。'},
            'medium_tree': {'label': '中型树', 'description': '中等树高、较轻树冠，示意串钱柳和无忧树。'},
            'shrub': {'label': '灌木', 'description': '低矮密集冠团，示意山茶、软枝黄蝉和大红花。'},
            'spreading': {'label': '开阔冠形', 'description': '低分枝、横向伸展冠形，示意鸡蛋花。'},
            'slender': {'label': '细高型', 'description': '细长树干、较窄冠形，示意落羽松。'},
        },
        'plants': plants, 'points': points, 'sources': list(SOURCES.values()),
        'limitations': ['未获得全校树木普查或逐株经纬度；全部标记是近似区域。',
                        '未获取可核实的校园100种植物逐株数据，使用崇基学院更明确的湖区资料。',
                        '植物资料主要来自2023年文章；当前存活、移植、树高和花期状态未经现场核对。',
                        '同一湖区的标签为避免重叠使用不同展示锚点，不表示每种植物只生长在该点。',
                        '树型和鸟动画是解释性视觉，不能用于物种鉴定、树木管理或生态监测。']}
    assert 5 <= len(plants) <= 12 and 3 <= len(points) <= 8
    assert len({p['id'] for p in plants + points}) == len(plants) + len(points)
    assert {p['visualType'] for p in plants} == set(data['visualTypes'])
    for item in plants + points:
        assert item['confidence'] == 'approximate' and item['locationType'] == 'area'
        assert item['source'] and all(s['url'].startswith('https://') for s in item['source'])
        assert all(math.isfinite(v) for v in item['position'])
        assert all(data['sample']['bounds']['min'][i] <= v <= data['sample']['bounds']['max'][i]
                   for i, v in enumerate(item['position']))
    target = PUBLIC / 'ecology.json'
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(plants)} plant areas + {len(points)} ecology points; {target.stat().st_size} bytes; checks passed')


if __name__ == '__main__':
    build()
