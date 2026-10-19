"""Typeset existing square renders; no grading, filters, crop, or geometry changes.

python artifacts/cuhk/compose_plan_styles.py
python artifacts/cuhk/compose_plan_styles.py --contact-only
python artifacts/cuhk/compose_plan_styles.py --check
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent / "plan_styles_20261004"
WIDTH, MARGIN, HEADER, FOOTER = 3000, 150, 270, 230
IMAGE_SIZE = WIDTH - 2 * MARGIN
HEIGHT = HEADER + IMAGE_SIZE + FOOTER
ORTHO_SPAN_M = 2250
STYLES = (
    ("A", "自然导览", "NATURAL GUIDE", "A_natural.png", "#F5F6EE", "#273E35", "#627265"),
    ("B", "纯白沙盘", "WHITE MAQUETTE", "B_paper.png", "#F7F6F2", "#383B3B", "#777D7B"),
    ("C", "珊瑚薄荷", "CORAL & MINT", "C_pastel.png", "#FAF3EB", "#574340", "#967F74"),
    ("D", "深蓝图谱", "BLUEPRINT", "D_blueprint.png", "#162D3B", "#EAF3F1", "#A1BDBF"),
)


def font(size, bold=False):
    candidates = ("msyhbd.ttc", "msyh.ttc", "simhei.ttf") if bold else ("msyh.ttc", "simhei.ttf")
    for name in candidates:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("A Chinese font is required: Microsoft YaHei or SimHei.")


def compose(raw, style):
    if raw.width != raw.height:
        raise ValueError(f"Expected an uncropped square render, received {raw.size}")
    letter, title, english, _, paper, ink, muted = style
    page = Image.new("RGB", (WIDTH, HEIGHT), paper)
    picture = raw.convert("RGBA").resize((IMAGE_SIZE, IMAGE_SIZE), Image.Resampling.LANCZOS)
    page.paste(picture, (MARGIN, HEADER), picture)
    draw = ImageDraw.Draw(page)
    draw.text((MARGIN, 57), "CUHK  /  香港中文大学", font=font(35), fill=muted, anchor="lt")
    draw.text((MARGIN, 128), f"{letter}  {title}", font=font(79, True), fill=ink, anchor="lt")
    draw.text((WIDTH - MARGIN - 170, 171), english, font=font(31), fill=muted, anchor="rt")
    arrow_x = WIDTH - MARGIN - 27
    draw.line((arrow_x, 197, arrow_x, 138), fill=ink, width=4)
    draw.line((arrow_x - 13, 156, arrow_x, 138, arrow_x + 13, 156), fill=ink, width=4)
    draw.text((arrow_x, 93), "N", font=font(29, True), fill=ink, anchor="mt")

    footer_y = HEADER + IMAGE_SIZE + 72
    draw.text((MARGIN, footer_y), "基于现有校园模型 · 风格研究", font=font(33), fill=ink, anchor="lt")
    draw.text((MARGIN, footer_y + 57), "ORTHOGRAPHIC CAMPUS PLAN", font=font(25), fill=muted, anchor="lt")
    # Scale follows the displayed map width, not the surrounding page width.
    bar_width = round(IMAGE_SIZE * 250 / ORTHO_SPAN_M)
    x2, y = WIDTH - MARGIN, footer_y + 32
    x1 = x2 - bar_width
    draw.line((x1, y, x2, y), fill=ink, width=4)
    for x in (x1, x2):
        draw.line((x, y - 9, x, y + 9), fill=ink, width=4)
    draw.text((x1, y + 23), "0", font=font(24), fill=muted, anchor="lt")
    draw.text((x2, y + 23), "250 m", font=font(24), fill=muted, anchor="rt")
    return page


def contact_sheet(pages):
    width, margin, gap, header = 2400, 60, 36, 148
    tile_w = (width - 2 * margin - gap) // 2
    tile_h = round(tile_w * HEIGHT / WIDTH)
    sheet = Image.new("RGB", (width, header + 2 * tile_h + gap + margin), "#E7E8E2")
    draw = ImageDraw.Draw(sheet)
    draw.text((margin, 45), "CUHK  /  校园俯视 · 四种方向", font=font(47, True), fill="#293E38", anchor="lt")
    for index, page in enumerate(pages):
        if page.size != (WIDTH, HEIGHT):
            raise ValueError(f"Unexpected page dimensions: {page.size}")
        x = margin + (index % 2) * (tile_w + gap)
        y = header + (index // 2) * (tile_h + gap)
        sheet.paste(page.resize((tile_w, tile_h), Image.Resampling.LANCZOS), (x, y))
    if len(pages) != 4:
        raise ValueError("The comparison requires all four style pages.")
    return sheet


def check():
    """One in-memory layout check; leaves no placeholder render files behind."""
    raw = Image.new("RGB", (100, 100), "#507896")
    pages = [compose(raw, style) for style in STYLES]
    assert all(page.size == (3000, 3200) for page in pages)
    assert all(page.getpixel((MARGIN + 20, HEADER + 20)) == (80, 120, 150) for page in pages)
    assert round(IMAGE_SIZE * 250 / ORTHO_SPAN_M) == 300
    assert contact_sheet(pages).width == 2400
    try:
        compose(Image.new("RGB", (100, 99)), STYLES[0])
    except ValueError:
        pass
    else:
        raise AssertionError("A non-square source must not be stretched into a map")
    print("PASS: full map preserved, page/contact dimensions, metric scale, square-source guard")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contact-only", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
        return
    required = [ROOT / (style[3] if args.contact_only else f"raw_{style[0]}.png") for style in STYLES]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Waiting for all four images:\n" + "\n".join(missing))
    pages = []
    for path, style in zip(required, STYLES):
        with Image.open(path) as source:
            page = source.convert("RGB") if args.contact_only else compose(source, style)
        pages.append(page)
        if not args.contact_only:
            destination = ROOT / style[3]
            page.save(destination)
            print(destination)
    destination = ROOT / "contact-sheet.png"
    contact_sheet(pages).save(destination)
    print(destination)


if __name__ == "__main__":
    main()
