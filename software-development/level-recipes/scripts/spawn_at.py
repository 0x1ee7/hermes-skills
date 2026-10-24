"""Move the player spawn of a generated map for a capture: `spawn_at.py MAP X Y [under]`.

The map is generated: restore it with `python3 tools/maps/build_levels.py` afterwards. The old
spawn tile takes the character to its left. With `under`, the spawn goes into the
`[level -1 at X0 Y0]` block instead of the ground grid.
"""
import re
import sys

path, x, y = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
under = len(sys.argv) > 4 and sys.argv[4] == "under"
lines = open(path, encoding="utf-8").read().split("\n")

for i, line in enumerate(lines):
    if "@" in line and not line.startswith("//"):
        j = line.index("@")
        lines[i] = line[:j] + (line[j - 1] if j > 0 else ",") + line[j + 1:]
        break

if under:
    header = next(i for i, l in enumerate(lines) if l.startswith("[level -1"))
    x0, y0 = map(int, re.match(r"\[level -1 at (\d+) (\d+)\]", lines[header]).groups())
    rows = [i for i in range(header + 1, len(lines)) if lines[i] and not lines[i].startswith("//")]
    row = rows[y - y0]
    line = lines[row].ljust(x - x0 + 1)
    assert line[x - x0] not in " #", f"({x}, {y}) is {line[x - x0]!r} below"
    lines[row] = line[:x - x0] + "@" + line[x - x0 + 1:]
else:
    grid = next(i for i, l in enumerate(lines) if l and not l.startswith("//"))
    line = lines[grid + y]
    lines[grid + y] = line[:x] + "@" + line[x + 1:]
open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
print("spawn at", x, y, "below" if under else "")
