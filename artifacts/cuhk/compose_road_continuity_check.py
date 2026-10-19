"""Place the two unmodified Blender renders side by side with inspection captions."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
before = Image.open(ROOT/'road_continuity_before.png').convert('RGB')
after = Image.open(ROOT/'road_continuity_after.png').convert('RGB')
assert before.size == after.size == (1600, 1200)
header, footer, gutter = 112, 138, 24
canvas = Image.new('RGB', (before.width*2+gutter, before.height+header+footer), '#15242a')
canvas.paste(before, (0, header))
canvas.paste(after, (before.width+gutter, header))
draw = ImageDraw.Draw(canvas)
bold = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 36)
regular = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 25)
small = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
for x, title, source in [(26, '修复前  |  相接路段标高错位', 'CUHK_photo_rebuilt.blend'),
                         (before.width+gutter+26, '修复后  |  共享节点连续衔接', 'CUHK_connected_roads.blend')]:
    draw.text((x, 16), title, font=bold, fill='#f0eee4')
    draw.text((x, 65), source, font=regular, fill='#b7c7c7')
bottom = header+before.height
draw.text((26, bottom+18), '真实 Blender 检查图：同一相机、光照与琥珀色路段高亮；建筑及地形保留，标签与植被统一隐藏。', font=regular, fill='#f0eee4')
draw.text((26, bottom+61), '检查位置  XY (305.43, 205.13) m  ·  OSM 节点 2231906278  ·  路段 213510397 / 213510536', font=small, fill='#b7c7c7')
draw.text((26, bottom+94), '仅对现有示意模型检查连续性；未引入新的实测高程。拼图仅增加标题与边距，未修改渲染像素。', font=small, fill='#b7c7c7')
canvas.save(ROOT/'road_continuity_comparison.png')
assert canvas.crop((0,header,1600,header+1200)).tobytes() == before.tobytes()
assert canvas.crop((1624,header,3224,header+1200)).tobytes() == after.tobytes()
print('COMPARISON_READY', canvas.size)
