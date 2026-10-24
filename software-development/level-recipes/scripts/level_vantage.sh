#!/usr/bin/env bash
# Capture a generated level from a temporary vantage point: moves '@' in assets/maps/LEVEL.map to
# (X, Y) (the old '@' becomes the tile to its left), sets the camera's default zoom and optional
# quarter turns, builds, captures `demo LEVEL`, then restores both files, also on failure.
# Usage: REPO=/d/dev/iso-engine SCRATCH=/c/.../scratch SCRATCH_W=C:/.../scratch \
#        level_vantage.sh NAME LEVEL X Y ZOOM [QUARTER_TURNS] [WAIT_MS]
# Needs capture_level.ps1 next to this script. Spell the paths out: background shells lose them.
set -euo pipefail
name=$1; level=$2; x=$3; y=$4; zoom=$5; turns=${6:-0}; wait_ms=${7:-5000}
: "${REPO:?set REPO}" "${SCRATCH:?set SCRATCH}" "${SCRATCH_W:?set SCRATCH_W (Windows form)}"
here=$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)
cd "$REPO"
map="assets/maps/$level.map"
cp "$map" "$SCRATCH/lv_map.bak"
cp game/demo/src/camera.rs "$SCRATCH/lv_camera.bak"
restore() {
  cp "$SCRATCH/lv_map.bak" "$map"
  cp "$SCRATCH/lv_camera.bak" game/demo/src/camera.rs
}
trap restore EXIT
python3 - "$map" "$x" "$y" <<'EOF'
import sys
path, x, y = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
lines = open(path, encoding="utf-8").read().split("\n")
start = next(i for i, l in enumerate(lines) if not l.startswith("//"))
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "")
grid = [list(l) for l in lines[start:end]]
for row in grid:
    for i, ch in enumerate(row):
        if ch == "@":
            row[i] = row[i - 1]
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
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$here/capture_level.ps1" \
  -Exe "$(cygpath -w "$REPO")\\target\\debug\\demo.exe" -WorkDir "$(cygpath -w "$REPO")" \
  -Level "$level" -Out "$SCRATCH_W/$name" -WaitMs "$wait_ms"
grep -E "WARN  (demo|engine_)|ERROR|panicked" "$SCRATCH/$name.log" || true
