# Editing the text map with one-off scripts

Painting dozens of scatter letters or placing many objects by hand is error-prone; a short
Python script run once (kept in scratch, not committed) is faster and repeatable. The map file
stays the hand-editable source of truth.

## Skeleton

```python
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
lines = text.split("\n")
start = next(i for i, l in enumerate(lines) if not l.startswith("//"))      # first grid row
end = next(i for i in range(start, len(lines)) if lines[i].strip() == "")  # blank after grid
grid = [list(l) for l in lines[start:end]]
# ... edit grid[y][x] (only where the ground char allows) ...
lines[start:end] = ["".join(r) for r in grid]
text = "\n".join(lines)
# Replace a section by splitting on WHOLE header lines, never on a bare "[scatter]" (the file's
# header comment mentions it):
head, rest = text.split("\n[scatter]\n", 1)
_, tail = rest.split("\n[objects]\n", 1)
text = head + "\n" + NEW_SCATTER + "\n[objects]\n" + tail
open(path, "w", encoding="utf-8", newline="\n").write(text)   # LF only
```

## Rules
- Copy the map to scratch before every run; `cmp` it afterwards when a run was experimental.
- Seed any randomness (`random.Random(404)`) so a rerun gives the same map.
- Change only tiles whose current character is the expected ground (`,` grass, `%` field).
- When placing a model, clear blocking scatter letters (`TPFDbrs`) under its footprint plus
  about 0.3 m, using the model's overall size from the build output; turned models (E/W) swap
  width and depth.
- Assert every `str.replace` target occurs exactly once before replacing (moving an object).
- Run the native Python with Windows paths (`C:/...`); MSYS paths are not translated.
- Afterwards: `cargo test -p demo` (map parses, keys exist, doors open) and a capture.
