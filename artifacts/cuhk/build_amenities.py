"""Build static dining / shuttle-stop labels from CUHK's published map points.

Use the same bundled Python and cached pyproj as prepare_data.py. No installs.
"""
import json
import math
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path.home() / '.agent-reach/cuhk'
sys.path.insert(0, str(CACHE / 'python'))
from pyproj import Transformer

MAP = 'https://www.cuhk.edu.hk/chinese/campus/cuhk-campus-map.html'
DATABASE = 'https://www.cuhk.edu.hk/chinese/js/campus/cuhk_location_db.js?20200915'
DINING = 'https://www.cuhk.edu.hk/chinese/campus/accommodation.html'
TRANSPORT = 'https://transport.cuhk.edu.hk/wp-content/uploads/documents/Shuttle.pdf'
RELOCATION = 'https://transport.cuhk.edu.hk/newsdetails/bus-stop-temporary-relocation-campus-circuit-east-downwards/'
TRANSPORT_NEWS = 'https://transport.cuhk.edu.hk/'

# Official facility IDs mapped to the existing scene's building IDs.
# Student and staff venues remain separate records at their published positions.
DINING_BUILDINGS = {
    '400': '135265606', '399': '135265606', '391': '135265606',
    '14': '923320403', '16': '134408688', '17': '134408688',
    '19': '135193913', '20': '135193913', '237': '3086286',
    '332': '135904508', '230': '193128663', '229': '421850856',
    '309': '194547399', '315': '194547401', '316': '194547401',
    '249': '194547402', '300': '194547402',
}
# Current shuttle locations supported by both the campus map and the 2026 diagram.
# Exclude old Residence 3/4 and Residence 10 names, and all light-bus-only records.
BUS_IDS = {'1', '2', '4', '5', '6', '7', '8', '9', '10', '15', '18',
           '20', '21', '22', '23', '24', '51', '52', '53', '55', '56',
           '62', '63', '64', '66'}


def build():
    cached = CACHE / 'amenities/cuhk_location_db.js'
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(urllib.request.urlopen(DATABASE, timeout=30).read())
    raw = cached.read_text(encoding='utf-8-sig')

    def section(name):
        match = re.search(r'\n' + name + r'\s*:\s*(\[.*?\])\s*,?\s*\n\s*\w+\s*:', raw, re.S)
        return json.loads(match.group(1))

    model = ROOT / 'cuhk-campus-web/public'
    buildings = {b['id']: b for b in json.loads((model / 'model/buildings.json').read_text(encoding='utf-8'))}
    terrain = json.loads((model / 'campus/heightfield.json').read_text(encoding='utf-8'))
    transform = Transformer.from_crs(4326, 2326, always_xy=True)

    def point(lat_lng):
        lat, lon = map(float, lat_lng.strip('()').split(','))
        east, north = transform.transform(lon, lat)
        return lat, lon, east - 839400, -(north - 831150)

    def ground(x, z):
        col = max(0, min(terrain['cols'] - 2, math.floor((x - terrain['xmin']) / terrain['step'])))
        row = max(0, min(terrain['rows'] - 2, math.floor((z - terrain['zmin']) / terrain['step'])))
        return max(terrain['heights'][r * terrain['cols'] + c]
                   for r in (row, row + 1) for c in (col, col + 1))

    items = []
    for food in section('facilities'):
        facility_id = food['facilities_id']
        if facility_id not in DINING_BUILDINGS:
            continue
        building = buildings[DINING_BUILDINGS[facility_id]]
        lat, lon, x, z = point(food['lat_lng'])
        y = max(ground(x, z), building['position'][1] + building['size'][1] / 2) + 4
        items.append({
            'id': 'canteen-' + facility_id, 'type': 'canteen',
            'name': food['facilities_name_en'], 'name_en': food['facilities_name_en'],
            'name_zh': food['facilities_name_xb5'],
            'position': [round(x, 3), round(y, 3), round(z, 3)],
            'latitude': lat, 'longitude': lon, 'buildingId': building['id'],
            'address': food['address_xb5'],
            'locationNote': food['address_xb5'] + ' · 校方地圖參考位置；具體入口請參照現場指示。',
            'source': DINING, 'sourceLabel': '香港中文大學餐飲名錄與校園地圖',
            'coordinateSource': DATABASE, 'officialFacilityId': facility_id,
        })

    for stop in section('shuttle_bus_stops'):
        stop_id = stop['bus_stop_id']
        if stop_id not in BUS_IDS:
            continue
        lat, lon, x, z = point(stop['lat_lng'])
        note = '校方地圖參考站點；實際停靠及臨時安排請查看校巴通告。'
        item = {
            'id': 'bus-stop-' + stop_id, 'type': 'bus_stop',
            'name': stop['bus_stop_name_en'] + ' Shuttle Bus Stop',
            'name_en': stop['bus_stop_name_en'] + ' Shuttle Bus Stop',
            'name_zh': stop['bus_stop_name_xb5'] + '校巴站',
            'position': [round(x, 3), round(ground(x, z) + 2.5, 3), round(z, 3)],
            'latitude': lat, 'longitude': lon,
            'locationNote': note, 'source': MAP,
            'sourceLabel': '香港中文大學校園地圖／交通處',
            'coordinateSource': DATABASE, 'officialBusStopId': stop_id,
            'secondarySources': [TRANSPORT],
        }
        if stop_id in {'62', '63'}:
            item['locationNote'] = '此站近期有臨時遷移通告。標記為校方地圖原位置，請查看校巴通告確認上車點。'
            item['secondarySources'].append(RELOCATION if stop_id == '63' else TRANSPORT_NEWS)
        items.append(item)

    assert len(items) == len(DINING_BUILDINGS) + len(BUS_IDS)
    assert len({item['id'] for item in items}) == len(items)
    for item in items:
        x, y, z = item['position']
        assert all(math.isfinite(value) for value in (x, y, z))
        assert -1200 <= x <= 1200 and -1200 <= z <= 1200 and 0 <= y <= 250
        assert item['source'].startswith('https://') and item['coordinateSource'] == DATABASE
        assert '\ufffd' not in item['name_zh'] and item['name_zh']
    data = {
        'updatedAt': date.today().isoformat(),
        'coordinateSystem': 'WGS84 transformed to EPSG:2326; Three.js [E-839400, label elevation HKPD, -(N-831150)]',
        'coverage': '17 dining venues covering all nine colleges and Benjamin Franklin Centre; 25 published campus-shuttle stop points. Static map points, not live boarding locations. See AMENITY_SOURCES.md for omissions.',
        'sources': [
            {'label': 'CUHK dining directory', 'url': DINING},
            {'label': 'CUHK campus map', 'url': MAP},
            {'label': 'CUHK map coordinates', 'url': DATABASE},
            {'label': 'CUHK shuttle diagram effective 1 September 2026', 'url': TRANSPORT},
            {'label': 'Transport Office notices', 'url': TRANSPORT_NEWS},
        ],
        'items': items,
    }
    output = model / 'campus/amenities.json'
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{output}: {len(DINING_BUILDINGS)} dining venues, {len(BUS_IDS)} shuttle-stop points; validation passed.')


if __name__ == '__main__':
    build()
