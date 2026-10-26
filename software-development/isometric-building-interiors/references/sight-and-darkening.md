# Sight and darkening

What the character itself can see is a system of its own: it hides or darkens what lies out of
sight, and never fades a wall.

## Sight against boxes, with straight edges
- Blockers are boxes on the ground plane: straight runs of storey-high walls, posts, shut doors,
  and solid models taller than the eye, by their footprint (trees and low props are not).
  Windows and open doors let sight through.
- Cast one ray along the middle of each of a few thousand sectors round the eye (4096 is fine),
  and stop it at the far side of the first box it crosses, so the boxes themselves are seen, or
  at the end of the cone (the near radius outside it). The drawn edge of what is seen then runs
  straight from the eye past the corners of what blocks it; sight worked out on the tile grid
  bleeds behind buildings and steps along tile edges.
- Hand the eye and the reach per sector to the renderer (a 1-D texture, uploaded only when the
  view changes); both shaders light a fragment within its sector's reach at full brightness,
  and read a per-tile memory elsewhere.
- Work the view out again whenever the eye moves or turns, a door opens or shuts or the settings
  change, and never while standing still. A few thousand ray-box tests a frame are cheap.
- Key a cached field on everything that changes it (the eye's tile or position, its facing,
  the doors, the switch), and filter by the cone after line of sight, not before. "Off" can be
  every tile of the storey in view, filled once, so consumers keep one membership test; land a
  query only with its first consumer, or `-D warnings` rejects it as dead code.

## On the tile grid instead
- Symmetric shadowcasting (Albert Ford, 2017) over one storey's cells with integer quadrants and
  `Row { depth, start, end }`; the slope is `(2*col - 1) / (2*depth)`, walls are revealed whole,
  floor tiles only where their centre passes `is_symmetric`, and the scan recurses at a wall's
  start and end. Keep the slopes f64. Stop the rows at the radius but gate only the reveal by
  squared distance: a tile beyond the radius still updates the row's slopes, and the next row
  is then out of range, so corners at the rim stay right.
- Tests: an open room; a wall column; a single wall with floor on both sides (its end's
  shadow); a pillar with a tile behind it; a low wall; the exact set inside a radius; off the
  map; the viewer's own tile; and symmetry from every floor tile of a map with pillars.
  Mutation traps: revealing every visited tile does not leak through a solid wall column, so
  only the symmetry test catches a lost `is_symmetric`; a solid wall column has no
  floor-to-wall transition, so a lost shadow-end update survives the wall test but not the
  isolated pillar's.

## Darkening what is not seen
- One tint per entity cannot vary inside a merged mesh (terrain in chunk meshes, one roof mesh
  per building). List how each kind of geometry is drawn before choosing per-entity writes;
  where any is merged, darken per fragment from a per-tile mask (an engine resource uploaded
  when it changes, sampled by every shader; an upright face takes the tile it faces, a tenth of
  a metre out along its normal). In view at full brightness, seen before about 55 %, never seen
  about 25 % (perceived brightness).
- Roofs: exempt them from the mask and shade each whole by the brightest of its building's tiles
  and the ring of tiles round it. Walls on edges hide every inside tile of a windowless
  building, so a roof lit by its inside alone stays dark while the character looks straight at
  the building.

## Between storeys
- The eye sees across the storey whose floor lies nearest its feet; half a metre or more up a
  flight, across the storey above from the stairwell (which then shows); down through open air
  onto the storeys below; never through a floor.

## The cone, and what moves
- The cone's heading: the body turns only while walking, and in third person left and right
  steer the camera, so a cone tied to the body points away from the view while the player
  steers standing still. In third person let the cone follow the camera's heading.
- Hide movers out of sight with a component eased at about 20 per second into the mesh tint's
  alpha, their shadows with them; they stay audible. Chain it after the pose systems and with
  the shadow follower, because the fade reads `Transform` while shadows write it.
- Tests: a wall's shadow starting at its corners along a straight line, a door opening it, a
  bus hiding what is behind it, the cone's width, the near radius all round, the storey
  chosen by the feet.
