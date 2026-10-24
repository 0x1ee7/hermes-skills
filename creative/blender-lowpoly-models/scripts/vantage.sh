#!/usr/bin/env bash
# Capture the iso-engine demo from a temporary vantage point: moves '@' in the map, sets the
# camera's default zoom (and optionally turns the iso view by quarter turns), builds, captures,
# then restores both files, also on failure.
# Usage: REPO=/d/dev/iso-engine SCRATCH=/c/.../scratch SCRATCH_W=C:/.../scratch \
#        vantage.sh NAME X Y ZOOM [QUARTER_TURNS] [WAIT_MS]
# Needs capture.ps1 next to this script. Afterwards `git status` must show no change to
# assets/maps/demo_world.map or game/demo/src/camera.rs that you did not make yourself.
set -euo pipefail
name=$1; x=$2; y=$3; zoom=$4; turns=${5:-0}; wait_ms=${6:-5000}
: "${REPO:?set REPO}" "${SCRATCH:?set SCRATCH}" "${SCRATCH_W:?set SCRATCH_W (Windows form)}"
here=$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)
cd "$REPO"
cp assets/maps/demo_world.map "$SCRATCH/vantage_map.bak"
cp game/demo/src/camera.rs "$SCRATCH/vantage_camera.bak"
restore() {
  cp "$SCRATCH/vantage_map.bak" assets/maps/demo_world.map
  cp "$SCRATCH/vantage_camera.bak" game/demo/src/camera.rs
}
trap restore EXIT
python3 - "$x" "$y" <<'EOF'
import sys
x, y = int(sys.argv[1]), int(sys.argv[2])
path = "assets/maps/demo_world.map"
lines = open(path, encoding="utf-8").read().split("\n")
start = next(i for i, l in enumerate(lines) if not l.startswith("//"))
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "")
grid = [list(l) for l in lines[start:end]]
for row in grid:
    for i, ch in enumerate(row):
        if ch == "@":
            row[i] = "."
# '@' takes the floor of the tile to its left: avoid water and walls there.
grid[y][x] = "@"
lines[start:end] = ["".join(r) for r in grid]
open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
EOF
sed -i "s/            zoom: 11.0,/            zoom: ${zoom},/" game/demo/src/camera.rs
if [ "$turns" != "0" ]; then
  python3 - "$turns" <<'EOF'
import sys, math
t = int(sys.argv[1])
p = "game/demo/src/camera.rs"
s = open(p, encoding="utf-8").read()
v = f"{t * math.pi / 2:.6}"
old = "            iso_yaw: 0.0,\n            iso_yaw_target: 0.0,"
assert s.count(old) == 1
s = s.replace(old, f"            iso_yaw: {v},\n            iso_yaw_target: {v},")
open(p, "w", encoding="utf-8", newline="\n").write(s)
EOF
fi
cargo build -q 2>&1 | grep -v "hard linking" | grep -v "^$" || true
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$here/capture.ps1" \
  -Exe "$(cygpath -w "$REPO")\\target\\debug\\demo.exe" -WorkDir "$(cygpath -w "$REPO")" \
  -Out "$SCRATCH_W/$name" -WaitMs "$wait_ms"
grep -E "WARN  (demo|engine_)|ERROR|panicked" "$SCRATCH/$name.log" || true
