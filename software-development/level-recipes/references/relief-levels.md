# Relief levels: heights, water, decks, storeys below the ground

Worked out on iso-engine's `terrain` level (`tools/maps/recipe_terrain.py`): a river valley
with a bridge, plank crossings, a ford, cliff-edged hills and a bunker reached by a stair and a
cave mouth. The kit side is `Canvas.relief` and friends in `tools/maps/levelkit.py`; the game
side is `[heights]`, `[decks]` and `[level -1 at X Y]` (docs/assets.md, "Maps").

## Kit calls
- `c.relief(base=-4.0, step=0.25, water=-2.6)`: heights per tile corner in `c.heights[y][x]`
  (metres, quantized on output), new kinds `rock gravel shallows asphalt concrete open`.
- `c.corner(x, y)`, `c.tile_corners(x, y)`, `c.centre_height(x, y)`, `c.steep(x, y)`.
- `c.deck(name, x0, y0, x1, y1, height, edges)`; `c.below(x, y, plan, name, note)`.
- `c.place(key, x, y, facing, height=H, stack=True)`: at a height, overlapping other stacked
  parts (spans over piers); `level=` is the most the ground may rise across a model's base.
- `c.reach(label, x, y, under=False)`: must be reachable from the spawn; reserves the tile.

## Compose heights in this order
1. Gentle bumps off the flat zones (roads and their verges, the river's surroundings).
2. Hills with `max` (a level top, cliffs round it, a ramp on one side at <= 0.7 m per m).
3. River with `min` (bed, beach, then a one-tile cliff or a ramp up the bank).
4. Roads forced level AFTER the river: a bank that reaches a road must not dent it.
5. Ground over storeys below forced up to their ceiling (the game refuses a lower crust).

## Pitfalls
- Bridge: the ground under a span must lie below its deck, or it pokes through the asphalt
  (z-fighting). Make the deck rectangle and the road ends meet the span models exactly, and
  widen the river's beach under the bridge so the bank breaks into a cliff at the bridge's ends.
- A guarded deck cannot be stepped off sideways, nor onto at a guarded end: split walkways into
  `name_on` (unguarded) / `name` (guarded over the water) / `name_off` (unguarded), all at one
  height. The kit's reachability links decks of equal height that touch.
- A reach goal on a steep tile is never reached: put it on the walkable tile just past a
  crossing, and recompute it when the banks change.
- Rock outcrops for "rocky edges": pick cliff tops (every steep neighbour lower), keep them off
  the ramps and crossings, space them (Manhattan >= 5), and cap the count.
- Scatter must keep off the ramps that tests walk up (`no_scatter` over them).
- Underground plans: stair tiles and cave-mouth tiles must be `open` on the ground storey, and
  the flight's landing on level ground at 0 m. Underground walls' tops sit exactly at the
  ground: the demo draws them 5 cm lower (`BURIED_WALL_GAP`), keep that when touching walls.
- Models with a canopy or steps: their base reaches out; a road tile under it fails `on=`.

## Tracing a real map from a picture (the Customs paper map)
- Measure offline with Pillow (`uv run --no-project --with pillow python ...`); the recipe stays
  standard library: write the measurements into it as data in the picture's pixels and convert
  with one scale (`paper(points)` -> tiles, e.g. 0.5 m a pixel). Changing the scale is then one
  number.
- Classify pixels by colour (river blue, yellow/white roads, black dashed rails, grey blocks,
  pink lots, dark green forest), then: river edges per row (centre and width), road and rail
  centre lines as the middle of their pixels per row or column in a window, blocks as connected
  components (their bounding boxes include drawn shadows: trim), forests as a mask at 4 m
  written as rows of `#`/`.` (split each row into two literals to stay within 100 columns).
- Check every measurement against the picture with vision crops; dashed lines and shadows
  confuse the classes (rail pixels pick up building shadows).
- Pick the scale from the buildings: the models must fit the picture's blocks (a 16 m
  warehouse in a 30-pixel block wants about 0.5 m a pixel).
- Paint roads and ballast with `near_line`/`paint_line`, never on river tiles nor under a
  bridge deck (the ground there must stay below the deck). Lay track pieces with `along(line,
  4.0)` at `height=SURFACE, stack=True` (with no height they sink to the lowest ground under
  them at banks); where a piece reaches over the river, a bridge span instead. A diagonal rail
  bridge cannot have a rectangular deck: leave it to look at.
- Place each traced block with a helper that tries the spot and small nudges and raises when
  nothing fits; ballast and roads beside blocks need the gaps measured (double track +-1.75 m
  plus 1.7 m of ballast each side).
- Put reach goals on open ground, never in the 1-tile slots between rows of containers.
- The game cuts a level tile's corner to its neighbours' ground where both share it
  (`terrain.rs`, `tile_triangles`), so diagonal roads read as straight; shallow angles still
  step.

## Debugging and looking
- Print corner heights and kinds for a window: run the recipe on a `Canvas` and print
  `c.corner(x, y)` / `c.terrain[y][x]` rows (the recipe raises `LevelError` on failure: catch it
  to still see the state).
- Reachability map: `c.reachable()` returns the reached nodes (`("g", x, y)` ground, `("d", i,
  x, y)` deck, `("u", x, y)` below); print `o` for reached tiles, `!` steep, `S` solid.
- In the game: `scripts/spawn_at.py MAP X Y [under]` moves `@` (under: into the `[level -1]`
  block), `scripts/capture_at.sh` launches, captures with the game-window-control skill and
  restores the map with `build_levels.py` (then `--check`).
