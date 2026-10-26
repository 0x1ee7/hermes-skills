#!/usr/bin/env bash
# The iso-engine's whole gate list, in order; exits 1 at the first red one, one summary line per
# gate. Needs gates.sh beside it. Never chain it into `&&` through a pipe: a pipeline's status is
# its last command's.
#
#   allgates.sh [nosmoke] [noassets]
#     nosmoke   skip the smoke run (headless work only; never for a commit that changes the
#               picture)
#     noassets  skip list_assets --check (a commit that adds assets: the closing commit
#               refreshes the list)
#
# REPO (default C:/Users/0x1de/dev/iso-engine) is the repo; LOGS (default: $TMPDIR, the scratch
# folder, never the skill's own) gets the full output of each gate.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-C:/Users/0x1de/dev/iso-engine}
export LOGS=${LOGS:-${TMPDIR:-$here}}
cd "$REPO" || exit 1
export SMOKE_CMD="ISO_EXIT_AFTER_FRAMES=120 ISO_AUDIO=0 cargo run -- testbed"
# The Vulkan loader's own warnings (wgpu_hal) are this machine's noise; the project's count.
export SMOKE_BAD="panicked| ERROR |WARN +(demo|engine_)"
smoke=smoke
assets=yes
for arg in "$@"; do
  case "$arg" in
  nosmoke) smoke= ;;
  noassets) assets= ;;
  *) echo "unknown argument $arg"; exit 2 ;;
  esac
done
bash "$here/gates.sh" $smoke doc || exit 1
AGENT_SCOPE='*' cargo test -p integration_tests >"$LOGS/g_integ.txt" 2>&1 ||
  { echo "integration (scope *): FAILED, see $LOGS/g_integ.txt"; exit 1; }
echo "integration (scope *): $(grep -c '^test .* ok$' "$LOGS/g_integ.txt") ok"
python3 tools/maps/build_levels.py --check >"$LOGS/g_py.txt" 2>&1 ||
  { echo "build_levels --check: FAILED, see $LOGS/g_py.txt"; exit 1; }
python3 tools/sound_recipe.py --check-credits >>"$LOGS/g_py.txt" 2>&1 ||
  { echo "sound_recipe --check-credits: FAILED, see $LOGS/g_py.txt"; exit 1; }
if [ -n "$assets" ]; then
  python3 tools/list_assets.py --check >>"$LOGS/g_py.txt" 2>&1 ||
    { echo "list_assets --check: FAILED, see $LOGS/g_py.txt"; exit 1; }
fi
echo "python checks: ok${assets:+ (asset list included)}"
