"""Compose level captures into one labelled contact sheet (summer left, winter right).

    python levels_sheet.py OUT.png CAPTURE_DIR lakeside:winter town:town_winter farm:farm_winter
Reads CAPTURE_DIR/sheet_<level>.png for each name, crops 6% off every side, scales each tile to
512x288, labels it with the level name and saves a 256-colour octree PNG (no dither).
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

TILE = (512, 288)
GAP = 4

out, captures = sys.argv[1], sys.argv[2]
rows = [pair.split(":") for pair in sys.argv[3:]]
cols = max(len(r) for r in rows)
sheet = Image.new("RGB", (cols * TILE[0] + (cols - 1) * GAP, len(rows) * TILE[1]
                          + (len(rows) - 1) * GAP), (30, 32, 38))
try:
    font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 19)
except OSError:
    font = ImageFont.load_default()
for row, names in enumerate(rows):
    for col, name in enumerate(names):
        shot = Image.open(os.path.join(captures, f"sheet_{name}.png")).convert("RGB")
        w, h = shot.size
        tile = shot.crop((int(w * 0.06), int(h * 0.06), int(w * 0.94), int(h * 0.94)))
        tile = tile.resize(TILE, Image.LANCZOS)
        draw = ImageDraw.Draw(tile)
        bounds = draw.textbbox((0, 0), name, font=font)
        draw.rectangle((8, 8, 8 + bounds[2] + 16, 8 + bounds[3] + 10), fill=(20, 22, 28))
        draw.text((16, 11), name, font=font, fill=(240, 240, 240))
        sheet.paste(tile, (col * (TILE[0] + GAP), row * (TILE[1] + GAP)))
sheet.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(
    out, optimize=True)
print(f"{out}: {os.path.getsize(out)} bytes, {sheet.size[0]}x{sheet.size[1]}")
