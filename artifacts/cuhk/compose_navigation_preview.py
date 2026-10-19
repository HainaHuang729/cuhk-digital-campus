"""Place existing navigation maps in phone frames without recolouring them."""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from compose_plan_styles import font


ROOT = Path(__file__).resolve().parent / "navigation_styles_20261004"
STYLES = (
    ("E", "01  浅绿导航", "#FFFDF7", "#89958A", "#F4E3BE", "#A29575", "#D0D7D0"),
    ("F", "02  蓝灰路网", "#8DA3AF", "#718A99", "#B4C6C7", "#86A5A9", "#E0E5E7"),
    ("G", "03  暖米地图", "#FFFEFA", "#A09382", "#E8C7A3", "#B59D7D", "#DFD9CE"),
    ("H", "04  薄荷步行", "#749589", "#5E7D74", "#A6C7B1", "#79A78E", "#DDE6DE"),
    ("I", "05  清晰灰白", "#596873", "#4E5D69", "#A7B4BC", "#8397A4", "#E4E8EB"),
    ("J", "06  夜间导航", "#91ACBC", "#6C899C", "#527B85", "#436470", "#304552"),
)
INK, MUTED = "#293B42", "#758087"


def phone(page, x, style, source, offset_y=0):
    """Use a uniform 2/3 reduction: all 900 × 1650 source pixels stay in frame."""
    _, title, road, road_edge, path, path_edge, building = style
    night = style[0] == 'J'
    ui_bg, ui_edge = ('#263D4B', '#3C5362') if night else ('#FAFCFA', '#D6DEDA')
    ui_ink, ui_muted = ('#DCE6EC', '#AABBC5') if night else (INK, MUTED)
    if source.size != (900, 1650):
        raise ValueError(f"Expected a 900 × 1650 map, received {source.size}")
    draw = ImageDraw.Draw(page)
    y, width, height = 280 + offset_y, 628, 1168
    draw.text((x + 14, 205 + offset_y), title, font=font(39, True), fill=INK, anchor="lt")
    draw.rounded_rectangle((x - 5, y + 13, x + width + 5, y + height + 13), radius=63, fill="#E3E7E4")
    draw.rounded_rectangle((x, y, x + width, y + height), radius=58, fill="#3B474D")
    draw.rounded_rectangle((x + 2, y + 2, x + width - 2, y + height - 2), radius=56, fill="#17242C")
    sx, sy = x + 14, y + 34
    page.paste(source.convert("RGB").resize((600, 1100), Image.Resampling.LANCZOS), (sx, sy))
    draw = ImageDraw.Draw(page)
    draw.rounded_rectangle((x + 266, y + 13, x + 362, y + 19), radius=3, fill="#68747A")
    draw.rounded_rectangle((x + 260, y + height - 18, x + 368, y + height - 13), radius=3, fill="#7D878B")

    # Static navigation framing only: no invented route, location, or controls.
    draw.rounded_rectangle((sx + 20, sy + 18, sx + 580, sy + 88), radius=20, fill=ui_bg, outline=ui_edge, width=1)
    draw.ellipse((sx + 42, sy + 39, sx + 64, sy + 61), outline=ui_muted, width=3)
    draw.line((sx + 61, sy + 58, sx + 71, sy + 68), fill=ui_muted, width=3)
    draw.text((sx + 89, sy + 37), "搜索校园地点", font=font(25), fill=ui_muted, anchor="lt")

    nx, ny = sx + 551, sy + 130
    draw.ellipse((nx - 27, ny - 13, nx + 27, ny + 65), fill=ui_bg)
    draw.text((nx, ny - 5), "N", font=font(19, True), fill=ui_ink, anchor="mt")
    draw.polygon(((nx, ny + 23), (nx - 12, ny + 53), (nx, ny + 46)), fill=ui_ink)
    draw.polygon(((nx, ny + 23), (nx + 12, ny + 53), (nx, ny + 46)), fill="#A1AEA9")

    legend_y = sy + 1019
    draw.rounded_rectangle((sx + 20, legend_y, sx + 580, legend_y + 61), radius=17, fill=ui_bg, outline=ui_edge, width=1)
    positions = (sx + 45, sx + 235, sx + 421)
    for px, label, colour in zip(positions, ("车行路", "步道", "建筑"), (road, path, building)):
        if label == "建筑":
            draw.rounded_rectangle((px, legend_y + 23, px + 27, legend_y + 39), radius=2, fill=colour, outline=road_edge)
        else:
            draw.line((px, legend_y + 31, px + 34, legend_y + 31), fill=path_edge if label == "步道" else road_edge, width=11)
            draw.line((px, legend_y + 31, px + 34, legend_y + 31), fill=colour, width=7)
        draw.text((px + 45, legend_y + 18), label, font=font(23), fill=ui_ink, anchor="lt")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--styles', default='EF')
    args = parser.parse_args()
    lookup = {style[0]: style for style in STYLES}
    if not args.styles or any(key not in lookup for key in args.styles):
        parser.error('Select styles from EFGHIJ')
    selected = [lookup[key] for key in args.styles]
    rows = (len(selected) + 1) // 2
    page = Image.new("RGB", (1600, 1610 + (rows - 1) * 1330), "#F1F3F0")
    draw = ImageDraw.Draw(page)
    draw.text((800, 65), "手机导航底图 · 样式预览", font=font(57, True), fill=INK, anchor="mt")
    draw.text((800, 145), "CUHK  /  香港中文大学", font=font(25), fill=MUTED, anchor="mt")
    for index, style in enumerate(selected):
        x = (118, 854)[index % 2]
        with Image.open(ROOT / f"mobile_{style[0]}.png") as source:
            phone(page, x, style, source, (index // 2) * 1330)
    draw = ImageDraw.Draw(page)
    draw.text((800, 1511 + (rows - 1) * 1330), "底图样式预览 · 路线与定位后续独立叠加", font=font(29), fill=MUTED, anchor="mt")
    destination = ROOT / ("phone-comparison.png" if args.styles == 'EF' else f"phone-comparison-{args.styles}.png")
    page.save(destination)
    print(destination)


if __name__ == "__main__":
    main()
