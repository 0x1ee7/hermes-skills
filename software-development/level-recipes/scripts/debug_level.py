"""Debug view of a recipe: the grid with model bases drawn over it.

    python debug_level.py RECIPE SEASON SEED      (env REPO, default D:/dev/iso-engine)
Bases of placed models print as their family's first letter in upper case (B building,
V vehicle, P prop, A animal, T tree); scatter as its letter; '*' marks door tiles.
"""
import importlib
import os
import sys
from pathlib import Path

MAPS = Path(os.environ.get("REPO", "D:/dev/iso-engine")) / "tools" / "maps"
sys.path.insert(0, str(MAPS))
import levelkit  # noqa: E402

for module in sorted(MAPS.glob("recipe_*.py")):
    importlib.import_module(module.stem)

recipe_name, season, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
lib = levelkit.Library()
fn, w, h = levelkit.RECIPES[recipe_name]
c = levelkit.Canvas(w, h, season, f"{recipe_name}:{seed}", lib)
fn(c)
try:
    c.check()
    print("check: ok")
except levelkit.LevelError as e:
    print("check:", e)
grid = [list(r) for r in c.render("debug", "debug", recipe_name, seed).split("\n")
        if r and not r.startswith("//")][:h]
for p in c.objects:
    _, base = (levelkit.turn(r, p.facing, p.x, p.y, p.scale) for r in lib.rects(p.key))
    for tx, ty in levelkit.tiles(base):
        if 0 <= ty < h and 0 <= tx < w:
            grid[ty][tx] = p.key.split(".")[0][0].upper()
for _, (dx, dy) in c.doors:
    grid[dy][dx] = "*"
print("     " + "".join(str(x // 10) for x in range(w)))
print("     " + "".join(str(x % 10) for x in range(w)))
for y, row in enumerate(grid):
    print(f"{y:3d}  " + "".join(row))
print(levelkit.summary(recipe_name, c))
