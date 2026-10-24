#!/usr/bin/env bash
# Per-item gates for a Cargo workspace. Prints one summary line per gate and exits 1 at the
# first red gate, so `gates.sh smoke && git add ... && git commit ...` never commits a red tree.
# Usage (from the workspace root): gates.sh [smoke] [doc]
# Env: LOGS       directory for the g_*.txt logs (falls back to TMPDIR; never left empty)
#      SMOKE_CMD  smoke run, default `ISO_EXIT_AFTER_FRAMES=120 cargo run`
#      SMOKE_OK   ERE that must match exactly one log line, default `exiting after [0-9]+ frames`
#      SMOKE_BAD  ERE that must match no log line, default `panicked| ERROR `; add the project's
#                 fallback warnings here
set -uo pipefail
LOGS="${LOGS:-${TMPDIR:?set LOGS (or TMPDIR) to a scratch directory}}"
SMOKE_CMD="${SMOKE_CMD:-ISO_EXIT_AFTER_FRAMES=120 cargo run}"
SMOKE_OK="${SMOKE_OK:-exiting after [0-9]+ frames}"
SMOKE_BAD="${SMOKE_BAD:-panicked| ERROR }"

red() {
  echo "$1: FAILED, see $2"
  exit 1
}

cargo fmt --all --check >"$LOGS/g_fmt.txt" 2>&1 || red fmt "$LOGS/g_fmt.txt"
cargo clippy --workspace --all-targets -- -D warnings >"$LOGS/g_clippy.txt" 2>&1 ||
  red clippy "$LOGS/g_clippy.txt"
echo "fmt, clippy: clean"
cargo test --workspace >"$LOGS/g_test.txt" 2>&1 || red tests "$LOGS/g_test.txt"
awk '/^test result:/ { p += $4; f += $6 } END { printf "tests: %d passed, %d failed\n", p, f }' \
  "$LOGS/g_test.txt"

for gate in "$@"; do
  case "$gate" in
  smoke)
    bash -c "$SMOKE_CMD" >"$LOGS/g_smoke.txt" 2>&1 || red smoke "$LOGS/g_smoke.txt"
    n=$(grep -cE "$SMOKE_OK" "$LOGS/g_smoke.txt")
    [ "$n" -eq 1 ] || red "smoke ($n exit lines)" "$LOGS/g_smoke.txt"
    if grep -qE "$SMOKE_BAD" "$LOGS/g_smoke.txt"; then
      red "smoke (unwanted log lines)" "$LOGS/g_smoke.txt"
    fi
    echo "smoke: ok"
    ;;
  doc)
    RUSTDOCFLAGS="-D warnings" cargo doc --no-deps --workspace >"$LOGS/g_doc.txt" 2>&1 ||
      red doc "$LOGS/g_doc.txt"
    echo "doc: clean"
    ;;
  *)
    echo "unknown gate: $gate (use smoke, doc)"
    exit 2
    ;;
  esac
done
