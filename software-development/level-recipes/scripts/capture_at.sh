#!/usr/bin/env bash
# Capture a generated level from a temporary spawn:
#   capture_at.sh REPO LEVEL NAME X Y [under] -- STEP...
# Moves the spawn (spawn_at.py), launches REPO/target/debug/demo.exe LEVEL with the
# game-window-control skill's gamewin.py, runs the steps (`@` in a step becomes
# $SCRATCH/NAME_, e.g. shot:@a.png), closes the game and rebuilds the maps (then --check).
# Build the demo first (cargo build -p demo). Pass native paths (C:/...), not /c/...
set -u
HERE=$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)
S=${SCRATCH:-${TMPDIR:-.}}
G=${GAMEWIN:-$HOME/AppData/Local/hermes/skills/software-development/game-window-control/scripts/gamewin.py}
R=$1; level=$2; name=$3; x=$4; y=$5; shift 5
under=""
if [ "${1:-}" = "under" ]; then under=under; shift; fi
[ "${1:-}" = "--" ] && shift
python3 "$HERE/spawn_at.py" "$R/assets/maps/$level.map" "$x" "$y" $under || exit 1
out=$(python3 "$G" launch --cwd "$R" --log "$S/game_$name.log" -- "$R/target/debug/demo.exe" "$level")
echo "$out" | tail -1
pid=$(echo "$out" | sed -n 's/^launched pid \([0-9]*\).*/\1/p')
steps=()
for step in "$@"; do steps+=("${step//@/$S/${name}_}"); done
python3 "$G" run --pid "$pid" "${steps[@]}" | grep -v "^ *[0-9.]* s "
python3 "$G" close --pid "$pid"
(cd "$R" && python3 tools/maps/build_levels.py >/dev/null && python3 tools/maps/build_levels.py --check)
