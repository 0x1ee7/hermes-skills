---
name: isometric-building-interiors
description: "Use when building or fixing isometric building interiors."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [isometric, rendering, cutaway, walls, line-of-sight, z-fighting, game-dev]
    related_skills: [rust-game-backlog-execution, game-window-control, level-recipes, game-camera-from-screenshot]
---

# Isometric building interiors

How buildings in an isometric game stay readable from outside, inside and upstairs: walls on
the edges between tiles (as Project Zomboid draws them), a see-through circle that shows the
player through whatever stands in front outside, a cutaway that opens only what hides the
player's room inside, a view field with straight edges, doors, and windows of glass. Worked out
on a wgpu engine whose walls and floors are sprite quads (sorted by layer, then far to near,
blended, depth-tested with writes) and whose doors, props and roofs are meshes. The rules hold
for any renderer that draws walls as thin faces.

## When to Use
- Adding or changing walls, doors, windows, storeys, roofs, the cutaway or the see-through
  circle in an isometric game.
- A screenshot shows lines, strips, holes or missing parts in or round buildings, walls cut that
  should stand, or doors that vanish.
- Line of sight: what the character sees, fog of war, darkening what it cannot see.
- Not for: laying out levels and generated buildings (`level-recipes`), the backlog loop and its
  gates (`rust-game-backlog-execution`), driving the game window (`game-window-control`).

## Support files
- `references/walls-on-edges.md`: the map format, faces, caps, posts, ends, finishes,
  colliders, groups; tops under an upper floor; windows of glass; doors; stairs; tile walls.
- `references/cutaway-and-see-through.md`: outside, the see-through circle; inside, the cutaway
  by rooms and lines of sight, and everything a lowered wall bares.
- `references/sight-and-darkening.md`: the view field with straight edges, darkening by tile,
  roofs, sight between storeys, hiding movers, the cone's heading.
- `references/verifying-visuals.md`: tests that state the visual condition, the states to check,
  captures (upper storeys too), mutations of content.

## Reading a screenshot

Map screen directions to the grid first: with the camera in the south-east, +x runs down-right
and +z down-left on screen, so artifacts lined up along one of those lie along a wall line.

| What the user sees | Usual cause | Where |
|---|---|---|
| Black dashes along wall lines on an upper floor | wall tops level with the floor drawn over them (z-fighting) | walls: tops under the storey above |
| A light or dark line along every wall top | tops lowered under faces that stand higher; the far face's back shows | walls: never lower a visible top |
| A dark vertical strip where walls meet | a lowered neighbour bares the hollow between a standing wall's faces, or a post side in the outside finish | cutaway: what a lowered wall bares |
| Doors gone inside a building | doors fade with their lowered wall and nothing stands in | walls: doors |
| Walls cut far from the player, every partition down | a rule that lowers everything with the inside behind it | cutaway: by rooms |
| A black doorway, a window that shows nothing | an opaque fill in the opening, opaque glass | walls: windows |
| The hollow of a wall seen through a window | sprite backs culled | walls: windows |
| The lit area bleeds behind buildings, ragged edges | sight on the tile grid | sight |

## Procedure for a visual report
1. Zoom into the screenshot (`vision_analyze` with `region`): name each artifact, which way it
   runs, what lies under it and on which storey; pick the cause from the table.
2. Reproduce it before changing anything: capture the same building from the same storey and
   view (`references/verifying-visuals.md`).
3. Write a test that states the visual condition itself (two visible quads coplanar and
   overlapping, a texture's alpha layout, the walls lowered from each side) and see it fail
   for the reported reason.
4. Fix the cause, then check every state the geometry can take: outside and inside, each storey
   shown and hidden, the four view turns, third person, doors open and shut. A fix that holds
   in one state can break another: tops lowered 2 cm cured the dashes upstairs and drew light
   lines along every wall once the storey above was hidden.
5. Mutation-check the guards, capture before and after, crop, zoom and look.

## Rules
- Never let two visible surfaces lie coplanar and overlap: draw order and `LessEqual` do not
  save them; rounding picks a winner per pixel, and every camera move reshuffles it.
- Whatever the cutaway lowers bares something its full height covered: list each (a
  neighbour's end, a post's side, a door, the top under a floor now hidden) and give it a part
  that shows in exactly that state.
- Lower only what hides the player's room from the camera's eye. A rule that ignores the room
  or the camera opens walls nobody needs opened.
- Finish every face, and every post side, by the tile it faces, never by the building alone.
- Openings are transparent, glass is translucent on one face only, and sprite quads draw both
  sides.
- Sight is rays against boxes, one reach per direction: the edge of what is seen runs straight
  from the eye past the corners of what blocks it.

## Pitfalls
- Test what the user sees, not a proxy: a test of the map cell misses a stale collider or
  texture, and a test that "something faded" misses what the circle should open.
- Overlap tests on quads need a millimetre of slack: edges that only touch look overlapping
  after rounding.
- A cached view (what the cutaway shows, what the eye sees) must key on everything that changes
  it: the player's room, the camera's heading and elevation, and a near camera's eye.
- A single-room test map hides every rule about partitions, rooms and storeys: test with three
  rooms and an upper storey.
