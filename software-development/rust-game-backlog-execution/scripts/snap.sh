#!/usr/bin/env bash
# snap.sh <label>: record the working tree (tracked and untracked files, nothing ignored) as a
# git tree object without touching the real index, and add "<label> <tree>" to
# $SNAP_DIR/snapshots.txt (taking a label again replaces its tree in place). Run from the
# repository root, after the gates passed on exactly this tree, with the commit message already
# in $SNAP_DIR/msgs/<label>.txt. Snapshots are cumulative: take them in order.
# commit_snapshots.py turns the list into commits.
set -euo pipefail
S=${SNAP_DIR:?set SNAP_DIR to a scratch folder}
label=${1:?usage: snap.sh <label>}
[ -f "$S/msgs/$label.txt" ] || { echo "no message $S/msgs/$label.txt"; exit 1; }
export GIT_INDEX_FILE=$S/snap.index
git read-tree HEAD
git add -A
tree=$(git write-tree)
unset GIT_INDEX_FILE
touch "$S/snapshots.txt"
if grep -q "^$label " "$S/snapshots.txt"; then
  awk -v l="$label" -v t="$tree" '$1 == l { print l " " t; next } { print }' \
    "$S/snapshots.txt" > "$S/snapshots.tmp"
else
  { cat "$S/snapshots.txt"; echo "$label $tree"; } > "$S/snapshots.tmp"
fi
mv "$S/snapshots.tmp" "$S/snapshots.txt"
echo "snapshot $label = $tree"
git diff --stat HEAD "$tree" | tail -1
