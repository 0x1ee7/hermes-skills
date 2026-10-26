# Walls on tile edges

## Map format
- One `[walls N at X Y]` block per storey on a double-resolution grid: even rows hold corners
  (`+`, `.` or a space) and north edges (`-` wall, `=` low wall, `0` window, `/` door); odd rows
  hold west edges (`|`, `=`, `0`, `/`) with each tile's middle between them. Row 0, column 1 is
  the north edge of tile (X, Y), row 1, column 0 its west edge.
- Load errors, each saying where: a character in the wrong direction, an edge off the map, an
  edge set twice. Once edges exist, refuse wall glyphs in the tile grid with a message that
  points at `[walls]`, so an old map fails loudly instead of growing tile walls.
- A `[buildings]` line names a rectangle, a roof and its colour, a wall material and a colour.

## Geometry
- An edge's wall is two long faces a thickness apart (0.15 m) and a cap. Where walls meet at an
  angle a post (a thickness square) fills the corner and the faces stop at its sides; walls in
  line abut. A free end, a door jamb, or the part of an end its neighbour in line does not
  cover, gets an end face.
- Give each face the part of its texture its world span covers (a `uv` rectangle), so nothing
  is squashed and the openings of a wall's two faces fall on the same spot. A face seen from
  its other side mirrors its texture: keep openings symmetric about the texture's middle.
- One collider per straight run of one height; doors break runs. One see-through group per
  straight run over every storey it stands on; a post is in the groups of both runs it joins.
- Each face takes the finish of the tile it faces: plaster inside a roofed building, else the
  building's material and colour; a default outside every building; concrete under the
  ground. Each post side takes the finish of the two tiles it faces (both inside: plaster). A
  post finished as a whole ("all four tiles inside, else outside") shows its outside material
  in a plaster room as a dark strip.
- On terrain a wall stands on the lower of its two corners. Walls under the ground stop a few
  centimetres short of the ground's crust, so the ground over them wins the depth test until
  the cutaway fades it.

## Tops under the storey above
- A wall's top level with the floor drawn over it z-fights it: black dashes along every wall
  below, upstairs, whatever the layer order.
- Do not lower the top a few centimetres: whenever the cutaway hides the storey above, the faces
  stand over the cap, and the back of the far face shows as a light line along every wall.
- Make the parts of a top under the storey above (under its floor, or under a wall on the same
  edge up there) separate sprites, hidden from the start and shown only on the highest storey
  the cutaway shows. A top covered in part splits into halves along its edge, a post's into
  quarters. Where no cutaway opens (walls outside every building), lowering those parts 2 cm
  is enough.

## Windows of glass
- Put translucent glass (about a third opaque, glints a little more) on the outer faces'
  texture behind an opaque frame and glazing bars, and frame a clear opening (alpha 0, so the
  texel is discarded) on the inside face's texture, on the same texels. The view crosses one
  pane from either side, and the far face, seen from behind through the glass, stands where
  the opening's reveal would be.
- That needs nothing new from a sprite pass that already sorts far to near, blends alpha
  "over" (a target alpha used as a shadow mask stays 1) and draws both sides of a quad. Pin the
  double-sided quads and the blend with tests once windows rely on them.
- Known compromises: the glass takes its wall's paint; a window whose faces are both outside
  shows two panes, one whose faces are both inside is an opening.
- Sight passes a window; walkers do not.

## Doors
- A leaf on its edge, hinged at one jamb, swinging into the building, shut at first. Shut, it
  blocks walking and sight like a wall: a collider fills the doorway (height 0 while open), and
  the sight blockers learn of the change at once.
- Double doors are doors in line on neighbouring edges: the second hinges on its far jamb, one
  press opens or shuts every leaf in line, and none shuts while a body stands in any of their
  doorways. Two presses for one double door felt wrong.
- Latch the key in a frame system and act in the fixed step, so the simulation changes on its
  own steps only.
- A door in a wall the cutaway lowers shows a low leaf (the leaf cut to the stand-in's height),
  turned with the door by a fixed system chained after the door system. The doorway's lintel
  goes whole with its wall; its jambs keep their end faces.
- An opening is transparent in its texture (alpha 0), never a dark fill: an opaque doorway
  hides the room behind it and reads as a black hole.

## Storeys and stairs
- A wall on the edge between a flight and its foot or its landing is a load error (walkers stop
  a step short). No banister where a wall runs along a flight, no railing where a wall stands
  at the stairwell's rim.
- Generated doors never open onto a flight's side: sweep a building generator with an oracle
  of its own (`level-recipes`).

## With tile walls (a whole tile thick)
- Group each wall tile in the group of its straight row piece and of its column piece (tiles
  contiguous along the line and stacked over storeys, two or more along it); a tile opens with
  either group. A piece every tile of which runs on further across it is a thick wall's
  thickness, not a wall: no group, or it opens alone and leaves a hole in the wall's top.
- Build the side of a tile against a neighbour in a group it is not in (normally culled as
  hidden), or a wall left standing beside an opened corner shows its hollow inside; and draw
  ground under every wall tile, or an opened wall shows the background through its footprint.
- A spawner that culls a face against an equally tall neighbour also culls the faces of an
  opening's reveal: exempt door and window neighbours, or the doorway looks into the hollow
  between the wall's front and back quads.
- A door needs a marker that survives the cutaway (a sill on the floor in a decal layer) and a
  floor under its tile; toggling it swaps face textures, the body's collider and the map cell,
  and invalidates the view field's key so sight passes on the same frame. Test the cell, the
  collider, the visible set and a face texture together.
