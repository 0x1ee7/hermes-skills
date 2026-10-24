---
name: level-recipes
description: "Use when generating tile-map levels from a model library."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [level-design, procedural, tile-map, iso-engine, recipes, seasons, python]
    related_skills: [blender-lowpoly-models, rust-game-backlog-execution]
---

# Generating levels from recipes

Build game levels as variations of one model library: a recipe lays out a kind of place on a
canvas, a season swaps every model for its seasonal form, a seed varies everything random. Maps
are generated files (never hand-edited), checked for overlaps and reachability before they are
written. Worked out on iso-engine (`tools/maps/`: `levelkit.py` kit, `recipe_*.py` recipes,
`build_levels.py` driver; text maps in `assets/maps/`), standard-library Python only.

## When to Use
- Add a level, a new kind of place, a winter/summer twin of a level, or seed variations.
- A test level for game features (buildings to enter, things to hide behind): place what matters
  exactly (`structure`, `place`, exact-tile scatter) and keep randomness to the edges; a summer
  level alone is fine.
- Debug a recipe that raises "does not fit" or "doors out of reach".
- Don't use for: building the models themselves (`blender-lowpoly-models`), hand-painted maps.

## How to Run (iso-engine)
```
python3 tools/maps/build_levels.py            # write every registered level
python3 tools/maps/build_levels.py --check    # exit 1 when a map differs from its recipe (CI)
python3 tools/maps/build_levels.py --list
python3 tools/maps/build_levels.py --recipe town --season winter --seed 7 --out x.map
```
Then `cargo run -- <level>`; the demo's tests cover every `level.*` key in the manifest.

## Procedure: add a kind of place
1. Sketch the layout in tile coordinates (x east, y south): roads first, then buildings facing
   them, then fixed props, then random clutter, scatter, animals, winter-only extras last.
   Keep tall scatter on the far edges (north, west: away from the default camera) and only low
   scrub plus a thin tree line on the near ones.
2. Write `tools/maps/recipe_<name>.py`: `@recipe(name, w, h)` over `def name(c)`, and
   `level(level_name, recipe, season, seed, title)` lines. Name models in their summer form.
   Done when `scripts/debug_level.py <recipe> summer 1` prints `check: ok`.
3. Use the kit, not hand-computed coordinates: `place(..., door=True)` lays door paths,
   `place_any(key, c.spots(area, facing))` puts clutter wherever it fits, a `frontage` helper
   (see references/kit-api.md) lines a street with buildings picked at random. Buildings to
   walk into, with storeys and stairs, are `structure(...)` plans (references/kit-api.md).
4. Run it in winter too (`debug_level.py <recipe> winter 1`); a model with no winter decision
   stops the build: add it to `WINTER` (its winter form, or None to put it away) or `NEUTRAL`.
5. `python3 tools/maps/build_levels.py`, add the `level.<name>` data key it asks for, capture
   with `scripts/level_vantage.sh` (overview at zoom ~30-36, a close view at ~12-16) and look.
   Done when captures show no overlaps, blocked doors or tall things hiding the place.
6. Commit per level (recipe + map + manifest key + README row), the winter twin separately,
   kit changes apart (prove with `--check` that existing maps did not change).

## Rules
- Same recipe + seed must give the same layout in every season: placements reserve the union
  of all a model's seasonal forms, put-away models (None) still reserve their space, and
  nothing season-specific draws from `c.rng` before the shared layout is finished.
- Overlap is checked exactly on whole extents (eaves, lamp arms), terrain and walkway clearance
  per tile on the base below knee height; `gap` (default 0.05 m) can go negative for fences.
- Every door must stay reachable from the spawn; the kit refuses to write a level otherwise.
- Generated maps carry a header naming recipe, season and seed; never edit them by hand.

## Pitfalls
- Place fixed pieces (fences, mailboxes, signposts) before random clutter, or the clutter takes
  their spot and the fixed `place` raises.
- A bus or van in a 3-tile street blocks it completely; streets with parked vehicles need 4.
- Lamp posts' arms count in their whole extent: face them over open ground or the street, not
  towards a house's eaves.
- Boats pulled up on a bank need `on=("ground", "water")`; ice extras need `on=("water",)`.
- Tile-granular overlap tests reject neighbours that are 5 cm apart; keep the exact test.
- A full-height wall under a flight's landing (its own storey) stops walkers short of the top;
  the game refuses such a map, so leave the tile under a landing open.
- `distance_to(...)` dicts must be iterated sorted, never as sets, or output changes per run.
- `why_not.py` runs the whole recipe, so it also reports models placed after the failure.
- Windows: foreground timeouts over 600 s turn into background jobs that lose exported
  variables; `.git/index.lock` from an editor's git integration needs a retry, not a delete.

## Verification
- `build_levels.py --check` says "N current"; `cargo test --workspace` passes (levels parse,
  only manifest models, spawn on open ground); each level smoke-runs without warnings.
- Overview and close captures of every new level were looked at; README picture refreshed
  with `scripts/levels_sheet.py`.

## Files
- `references/kit-api.md`: Canvas methods, roles, seasons, the frontage helper, debugging.
- `scripts/debug_level.py`: ASCII view of a recipe's result with model bases and doors.
- `scripts/why_not.py`: what blocks a model at a spot.
- `scripts/level_vantage.sh`: capture `demo <level>` from a temporary spawn and zoom, restoring
  the map and camera afterwards. It calls a `capture_level.ps1` next to it, which this skill
  does not ship: put one there before running it.
- `scripts/levels_sheet.py`: labelled summer/winter contact sheet for the README.
