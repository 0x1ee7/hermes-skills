"""Why does `key` not fit at (x, y)?

    python why_not.py RECIPE SEASON SEED KEY X Y FACING [ON]   (env REPO)
Runs the recipe (stopping at its first LevelError), then reports the spot's rectangles, the
placed models' whole extents it overlaps and the state of its base tiles. Models placed after
the failure point can show up too when the recipe did not stop there.
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

recipe_name, season, seed, key, x, y, facing = sys.argv[1:8]
on = tuple(sys.argv[8].split(",")) if len(sys.argv) > 8 else ("ground",)
x, y = float(x), float(y)
lib = levelkit.Library()
fn, w, h = levelkit.RECIPES[recipe_name]
c = levelkit.Canvas(w, h, season, f"{recipe_name}:{seed}", lib)
try:
    fn(c)
except levelkit.LevelError as e:
    print("recipe stopped:", e)
whole, base = c.footprints(key, x, y, facing, 1.0)
print("whole", [round(v, 2) for v in whole], "base", [round(v, 2) for v in base], "on", on)
for other in c.wholes:
    if levelkit.overlaps(whole, other):
        print("overlaps whole", [round(v, 2) for v in other])
for tx, ty in levelkit.tiles(base):
    print("base tile", (tx, ty), "terrain", c.terrain[ty][tx], "taken", c.taken[ty][tx])
