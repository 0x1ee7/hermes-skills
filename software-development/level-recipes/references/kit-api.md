# levelkit API (iso-engine `tools/maps/levelkit.py`)

## Canvas (one level under construction)
- `c.rng`: the layout's random generator (seeded by recipe name and seed).
- `c.winter`: True in the winter season; branch only for extras at the very end.
- Terrain: `fill(x0, y0, x1, y1, terrain)` with terrain `ground`, `path`, `lane` (dirt / trodden
  snow), `street` (cobbles, cleared in winter), `water` (ice in winter, walkable), `field`.
  `lake(cx, cy, rx, ry, wobble)` paints a wobbly ellipse of water; `distance_to("water")` maps
  tiles to their 8-neighbour distance (shore = 1).
- `no_scatter(x0, y0, x1, y1)`: greens, yards, pastures stay free of scatter.
- `set_spawn(x, y)`: '@' copies the floor of the tile to its left, which must match.
- Models: `place(key, x, y, facing="S", scale=1, group, margin, on=("ground",), door, gap)`
  raises `LevelError` when it does not fit; `fits(...)` asks; `place_any(key, spots, **kw)`
  takes the first spot that fits and returns it or None; `spots(area, facing, terrain)` lists
  free tile centres in random order. Facing: N/E/S/W (needed for doors), NE..., or degrees.
  `towards(x, y, tx, ty)` gives the facing that looks at a point.
- `margin` keeps scatter that many tiles from a model's base; `door=True` lays a path from the
  tile in front of the base to the nearest road (path, lane or street) and registers the door
  for the reachability check.
- `animals(key, count, area, where=None)`: random free tiles, random facing.
- `scatter(role, chance)`: chance is a number or `lambda x, y: ...`; roles (letter, terrain,
  solid, models per season): forest T, pines P, orchard F, bushes b, rocks r, stumps s, tufts g,
  flowers f, reeds R, pebbles o, wheat w (field), cabbage v (field).
- Trees on exact tiles: tree keys have no season decision, so `place` refuses them. Give the
  role a chance function that returns 1.0 there
  (`c.scatter("forest", lambda x, y: 1.0 if (x, y) in TREES else edge(x, y))`); the game picks
  the model per tile.

## Seasons
- `WINTER`: summer key -> winter key or None. `NEUTRAL`: keys fine in both seasons.
- `WINTER_ONLY`: winter forms plus extras such as `prop.snowman`; placing one in summer raises.

## A frontage helper (from recipe_town.py)
```python
def frontage(c, keys, start, end, front, facing, gap=0.6):
    along_x = facing in ("N", "S")
    pos = start
    while True:
        key = c.rng.choice(keys)
        whole, base = c.footprints(key, 0.0, 0.0, facing, 1.0)
        low, high = (whole[0], whole[2]) if along_x else (whole[1], whole[3])
        centre = pos - low
        if centre + high > end:
            return
        depth = {"S": -base[3], "N": -base[1], "E": -base[2], "W": -base[0]}[facing]
        x, y = (centre, front + depth) if along_x else (front + depth, centre)
        if c.fits(key, x, y, facing):
            c.place(key, x, y, facing, group="Buildings", margin=1, door=True)
            pos = centre + high + gap
        else:
            pos += 1.0
```
`front` is the line the fronts stand on (one tile back from the road keeps a pavement).

## Structures (tile-built, enterable buildings)
- `structure(x, y, plan, name=None, roof="gable", colour="red", notes=())`: `plan` is one list
  of rows per storey, ground first, in the map's own characters `# = . + c p ^ < >`. A space
  keeps the ground on the ground storey and is open air above. Upper storeys become
  `[level N at X Y]` blocks; blank rows round a block are trimmed and its origin moved, because
  the game reads them as padding.
- Named: a `[buildings]` entry over the ground storey's rectangle, eaves (0.3 m) that models
  keep clear of, no scatter a tile further out, and a door with a path for every floor tile on
  the rectangle's edge (corners aside). Lay roads first: each door path must reach one.
- Unnamed: freestanding walls, an outside stair. Register an outside stair's approach tile
  with `c.path_from("label", (x, y))` so the reachability check covers it.
- Flights: a floor at the foot, a floor on the storey above beyond the head, an open stairwell,
  and no tall wall under the landing on the flight's own storey. The game refuses that wall
  at load: walkers stop a step short of the top. Piers for an outside landing go under its
  low walls, never under the landing itself.
- Buildings open (roof, upper storeys, near walls) only while the player is inside one; behind
  a building the see-through circle shows the player instead. A test lane behind buildings
  exercises the circle, not an opening building.
- Prove a level's buildings with the demo's `walked_in` (stairs tests): a walk in at a door, up
  to the top storey and out, ending where it was headed. Keep crates and plants off the straight
  lines between doors and flights, so those walks stay straight.

## Debugging
- `debug_level.py RECIPE SEASON SEED`: grid with bases as B/V/P/A/T, doors as `*`, plus the
  summary line and the reachability result.
- `why_not.py RECIPE SEASON SEED KEY X Y FACING [on,terrains]`: whole/base rectangles, the
  wholes it overlaps and the terrain/taken state of each base tile.
- Typical fixes: move fixed pieces earlier, widen a street, turn a lamp, use `place_any` with
  `spots`, give boats water as allowed terrain.
