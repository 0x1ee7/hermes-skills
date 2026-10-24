#!/usr/bin/env bash
# List every site of one rustc/clippy warning as `path:line|source line`, sorted by file and line.
# Usage (from the workspace root): lint-sites.sh '<warning text prefix>' [cargo clippy args]
#   lint-sites.sh 'missing documentation' -- -W missing_docs
# Extra arguments go to `cargo clippy --workspace --all-targets`, so a lint can be switched on
# from the command line without touching Cargo.toml.
set -uo pipefail
pattern="${1:?usage: lint-sites.sh '<warning text prefix>' [cargo clippy args]}"
shift
cargo clippy --workspace --all-targets "$@" 2>&1 |
  grep -A2 "^warning: ${pattern}" |
  grep -E '^ +--> ' |
  sed -E 's/^ +--> //' |
  tr '\\' '/' |
  sort -t: -k1,1 -k2,2n | uniq |
  while IFS=: read -r file line _; do
    printf '%s:%s|%s\n' "$file" "$line" "$(sed -n "${line}p" "$file")"
  done
