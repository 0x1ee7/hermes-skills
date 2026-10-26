---
name: level-from-reference-image
description: "Use when tracing a map image into a tile level, or drawing a building from its floor plans."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [level-design, tracing, floor-plans, iso-engine, python, image]
    related_skills: [level-recipes, isometric-building-interiors]
---

# Levels from a reference image, buildings from floor plans

How the iso-engine `terrain` level (Customs) was laid out from a flat-coloured map image, and
its dorms drawn from floor plans. Companion to `level-recipes` (the kit and recipes).

## When to Use
- The user gives a map image or a 3D render and wants the level to follow it: roads, water,
  forests, building rectangles, railways, where bridges and underpasses go.
- The user gives floor plans and wants a building that matches them.
- Don't use for procedural levels with no reference (`level-recipes`).

## Procedure: image -> level
1. Look at the image first (`read` it, then grid-overlaid crops made with Pillow). Sample its
   palette (`Counter` of pixels): flat maps have a dozen exact colours (ground, forest, road,
   pad, water, building dark/grey, dirt, shingle, footpath, rails, markers, label text).
2. Copy the image into the repo (`tools/maps/reference/`) and write a tracing tool that turns
   it into a text file the recipe reads (`tools/maps/trace_customs.py` ->
   `customs_trace.txt`): size, frame in image pixels, one class character per tile, building
   rectangles, railways. The recipe must build without the image or Pillow/numpy/scipy.
3. Pick the tile scale from the smallest thing that must be walkable, not from the image's
   size: rooms 3-5 tiles across put the dorms at 12 by 30, which made the level 600 by 315
   tiles. Say so to the user.
4. Classify pixels by palette (tolerance ~10); ignore rails, markers and label text so they
   take the nearest known class (`distance_transform_edt` indices); take the class most of a
   tile's pixels have, with a lower claim for thin things (footpaths 0.2, roads 0.35).
5. Render the trace (3 px a tile, building boxes outlined) and look at it before going on.
6. Building rectangles: largest all-true rectangle of each blob (histogram method), then the
   next in what is left with a one-tile margin, so no two share a wall; drop rectangles under
   3 tiles on a side. The recipe builds `c.building(...)` on each, door towards the nearest
   road tile, retrying seeds when the generator refuses.
7. Railways: hint each by eye as points on the image, then pull them onto the dashes (resample,
   shift to the mean of rail pixels across the line, smooth, Douglas-Peucker). Double lines are
   traced down their middle and laid as two tracks `TRACK_GAP` apart. Overlay the result.
8. Bridges and underpasses the user marks: a road over water is a deck on spans and piers,
   the water joined under it by a river polyline; a road under rails is a cutting (corners
   along the road sink with a ramp of depth/0.4 each side, rails get `bridge.rail_span`
   over it). Other crossings stay level.
9. Put the spawn on a road tile whose west neighbour is road, list places that must stay in
   reach, build, then run the whole suite and capture spots with `game-window-control`
   (`prep-probe.py terrain X Y` from `rust-game-backlog-execution`).

## Procedure: building from floor plans (`dorms.py`)
1. Decide the scale from the rooms (a tile a metre, rooms at least 3 across), then lay each
   storey out in tile rectangles on paper before coding.
2. `StoreyPlan(rooms, halls, doors, flights, open_edges, quiet_edges)` per storey; rooms get a
   door onto the hall they share most wall with; halls are open to each other; windows go in
   the middle of outer runs. Stack flights: the next storey's stairwell tiles are left open
   automatically, the landing must be a floor there.
3. A building is a rectangle in the map format: an L is two buildings (wing and arm), the seam
   edges owned by one of them, the other lists them in `open_edges`; pass `adjoins` so their
   eaves may overlap.
4. `Canvas.authored(...)` refuses a room with no door, a flight with no floor at its foot or
   landing, a door onto a flight, an unreachable floor. Capture the ground storey, the lobby
   and an upper storey in game.

## Pitfalls
- A grid row can start with `#` (outside tiles): a "comment" test of `startswith("#")` drops
  those rows. Make comments `"# "`.
- Black outline lines drawn inside the play area (zone borders over the river) classify as
  outside; only background reaching the image border is outside. Others become unknown.
- Label text takes the pad or building colour at its edges: ignore its exact colour and drop
  building rectangles thinner than 3 tiles, or text becomes buildings.
- Specks beyond the outline become buildings whose doors cannot be reached: skip rectangles with
  an outside tile within 3 tiles.
- `Canvas.check` must count decks, or doors across a bridge are "out of reach".
- Wrecks, scatter and props placed at the ends of a deck block it: keep them 6 tiles off decks
  and call `no_scatter` round a narrow pipeline deck. A walk test then fails with the walker
  stuck at its start, not an error.
- Roads at an angle and a cutting: derive the road's axis from the road tiles round the
  crossing (PCA), not from the rail.
- Tests that walk a level fixture break when the layout changes: read decks from the layout
  (`layout.decks`) rather than hard-coding positions where you can.
- Python on Windows: `Path.write_text` writes CRLF; write bytes for tracked files.
