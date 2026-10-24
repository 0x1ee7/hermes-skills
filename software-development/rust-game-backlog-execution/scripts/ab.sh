#!/usr/bin/env bash
# A/B timing of two builds: alternate the before and the after binary, N runs each, print every
# run and the two means. Alternating spreads drift (clock boost, caches, other load) over both
# sides; a block of before runs followed by a block of after runs does not.
#
# Usage: ab.sh <before.exe> <after.exe> [runs=4] [args for the game ...]
# Env:   AB_ENV   environment for each run (default "ISO_VSYNC=0 ISO_EXIT_AFTER_FRAMES=1200")
#        AB_GREP  extended regex whose match holds the measure as its first number
#                 (default "app.update [0-9.]+")
# Build the before binary in a detached worktree with a CARGO_TARGET_DIR of its own.
before="$1"; after="$2"; runs="${3:-4}"; shift 3 2>/dev/null || shift $#
env_line="${AB_ENV:-ISO_VSYNC=0 ISO_EXIT_AFTER_FRAMES=1200}"
pattern="${AB_GREP:-app.update [0-9.]+}"
for i in $(seq 1 "$runs"); do
  for side in before after; do
    exe="$before"; [ "$side" = after ] && exe="$after"
    match=$(env $env_line "$exe" "$@" 2>&1 | grep -oE "$pattern" | head -1)
    echo "$side ${match:-<no match>}"
  done
done | awk '{ print } { if (match($0, /[0-9]+\.?[0-9]*/)) { v[$1] += substr($0, RSTART, RLENGTH); n[$1]++ } }
  END { for (s in v) printf "%s mean %.4f over %d runs\n", s, v[s] / n[s], n[s] }'
