"""Arrange unmodified Blender check renders into two pairs and a combined sheet."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
bold = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 33)
regular = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 23)
W, H, G, HEADER, FOOT = 1600, 1200, 24, 116, 104
panels = []
for view, title, coordinate in [
    ('bridgehead', '桥头路面与纵坡', 'XY (305.43, 205.13) m · OSM 路段 213510397 / 213510536'),
    ('hostel', '陈震夏宿舍旁路口与地形切口', '深切检查位置 XY (-255, 240) m · 相机保留宿舍基脚及周边三岔路口'),
]:
    images = [Image.open(ROOT/f'road_grading_{view}_{suffix}.png').convert('RGB') for suffix in ('before', 'after')]
    assert all(image.size == (W, H) for image in images)
    panel = Image.new('RGB', (W*2+G, HEADER+H+FOOT), '#15242a')
    draw = ImageDraw.Draw(panel)
    for side, image in enumerate(images):
        x = side*(W+G)
        panel.paste(image, (x, HEADER))
        draw.text((x+26, 14), f'{title}  |  {"上一版" if side == 0 else "整坡版"}', font=bold, fill='#f0eee4')
        draw.text((x+26, 64), 'CUHK_connected_roads.blend' if side == 0 else 'CUHK_roads_graded.blend', font=regular, fill='#b7c7c7')
        assert panel.crop((x,HEADER,x+W,HEADER+H)).tobytes() == image.tobytes()
    draw.text((26,HEADER+H+15), coordinate, font=regular, fill='#f0eee4')
    draw.text((26,HEADER+H+55), '真实 Blender 检查图 · 同一相机、光照和路面材质 · 统一隐藏标签与植被 · 仅拼接原始渲染像素', font=regular, fill='#b7c7c7')
    panel.save(ROOT/f'road_grading_{view}_comparison.png')
    panels.append(panel)
combined = Image.new('RGB', (panels[0].width, sum(panel.height for panel in panels)+G), '#273a41')
combined.paste(panels[0], (0,0))
combined.paste(panels[1], (0,panels[0].height+G))
combined.save(ROOT/'road_grading_comparison.png')
print('GRADING_COMPARISONS_READY', combined.size)
