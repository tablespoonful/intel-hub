"""PWA アイコン (worker/src/assets/) を生成する。

使い方:
    python -m scripts.gen_pwa_icons

SVG と PNG は同じ幾何 (512 グリッド上の 3 本の棒) から描く。図形は maskable の
安全領域 (中心から半径 40%) に収まるので、同じ画像を any / maskable の両方に使える。
生成物はコミット済みで、デザインを変えるときだけ実行する (Pillow が必要)。
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "worker" / "src" / "assets"

GRID = 512
BG = "#0d1117"
ACCENT = "#58a6ff"
RADIUS = 10
# (x, top, width), すべて下端 y=352 に揃える
BARS = [(144, 256, 56), (228, 192, 56), (312, 128, 56)]
BOTTOM = 352

PNG_SIZES = {"icon-192.png": 192, "icon-512.png": 512, "apple-touch-icon.png": 180}
SUPERSAMPLE = 4


def build_svg() -> str:
    rects = "".join(
        f'<rect x="{x}" y="{top}" width="{w}" height="{BOTTOM - top}" rx="{RADIUS}" fill="{ACCENT}"/>'
        for x, top, w in BARS
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}">'
        f'<rect width="{GRID}" height="{GRID}" fill="{BG}"/>{rects}</svg>\n'
    )


def build_png(size: int) -> Image.Image:
    big = size * SUPERSAMPLE
    scale = big / GRID
    img = Image.new("RGB", (big, big), BG)
    draw = ImageDraw.Draw(img)
    for x, top, w in BARS:
        box = (x * scale, top * scale, (x + w) * scale, BOTTOM * scale)
        draw.rounded_rectangle(box, radius=RADIUS * scale, fill=ACCENT)
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "icon.svg").write_text(build_svg(), encoding="utf-8")
    for name, size in PNG_SIZES.items():
        build_png(size).save(OUT_DIR / name, optimize=True)
    print(f"wrote icons to {OUT_DIR}")


if __name__ == "__main__":
    main()
