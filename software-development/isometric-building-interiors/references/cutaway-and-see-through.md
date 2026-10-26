# Cutaway and see-through circle

Outside a building the see-through circle shows the player through whatever stands in front;
inside, the cutaway opens the building round the player's room. Neither fades a whole wall,
roof or tree for being near.

## Outside: the see-through circle
- Open or fade only what stands between the camera and the player. A cause that ignores the
  camera (a cone in the way the player faces) makes walls the player walks up to see-through and
  shows what lies behind them. Pin it: a wall a few metres ahead of the player stays solid, with
  no circle in it, in the isometric view and in third person.
- Prefer a screen-space see-through circle to fading whole occluders. Fading a whole wall, roof
  or storey to about 0.3 opens far more than hides the player, and stacked translucent walls
  make large patchy shapes. The circle is a resource (centre at the chest, radius, strength)
  that the game eases and the renderer turns into NDC once per frame; the shaders open the
  flagged draws by screen distance alone, with a soft edge.
- Decide what the circle opens on the CPU, once a frame for the whole frame, for whole things,
  and pass it as a per-vertex or per-instance flag. Never compare each fragment's depth with
  the centre's: one plane through the chest slices any surface passing beside the player (a
  straight diagonal through the circle), and with a camera looking down, the tops of walls
  behind the player land in front of that plane.
- Judge boxes, not points: a box opens while the line of sight to the camera from the circle's
  centre, or from points on rings round it (0.3 and 0.6 of the radius, at the centre's depth,
  along the camera's right and screen-up), enters it from outside (slab test; along `-forward`
  for an orthographic camera, to the eye for a perspective one), or while its footprint lies
  wholly in front of the centre on the ground plane. One point per draw fails both ways: a bus
  whose middle lies behind still hides the player with one end, and a building beside the
  player whose middle is in front opens a hole beside it. A line that starts inside a box
  counts for nothing (eaves, a crown overhead). Quick reject: when the centre's line misses the
  box grown by the outer ring's reach in every axis, every ring line misses.
- Group the quads of walls. Judged quad by quad, a wall running past the player opens face by
  face, with straight edges at tile boundaries, and some faces open where the player is not
  hidden at all. With walls on edges, one group per straight run (edges in line on one storey,
  and the same edge on the storeys above and below); a post is in the groups of both runs it
  joins. A group opens whole by the box round its members. A straight run is convex, so if any
  of it hides part of the circle, the player lies behind every face of it the camera sees:
  opening it whole never opens a wall the player stands in front of. Never group a whole
  building or an L: the parts behind the player open too.
- Keep "opens" consistent across kinds: if lone things (a roof) open for lying wholly in
  front, groups must too, or the roof opens and the walls under it stay, which reads as a
  hollow box.
- Let the circle decide on its own: rays from the chest and the head to the eye against the
  occluders' boxes (slab test), never "something has faded". Skip parts the cutaway already
  took away.
- Mark occluders see-through through a component requirement (`#[require(SeeThrough)]`), so
  every spawn path gets it.

## Inside: the cutaway
- Open a building only while the player is inside it. A proximity rule ("open the building
  within a few metres that stands between the player and the camera") flips buildings open as
  the player walks past them, for example up an outside stair beside one; outside, the circle
  shows the player through.
- Keep whole-part fades for the cutaway alone (building parts eased to 0 or 1); one fader eases
  them and writes tint alpha only when it changes. Write a part's wish only when it changes,
  and visit only the building opened before and the one opened now.
- Never lower "every wall with the inside behind it from the camera": in a building of many
  rooms that drops every partition of the storey, and the user reads it as walls cut for no
  reason. Split each building into rooms at load (a flood fill over floors, flights and the
  stairwells over them, parted by storey-high walls, windows and doors) and lower only what a
  line of sight from the player's room's floor to the camera's eye crosses below the wall's
  top: 16 samples per tile, nudged off the diagonals so no line runs through a corner of the
  grid, walked edge by edge (DDA) for at most `wall height * run / rise` and never past the
  eye. That is the room's near walls and those just in front of it whose shadow from the
  camera falls on its floor. A near (third-person) eye lowers what stands between it and the
  room, nothing behind it.
- Key the cached view on the player's room and the camera's heading and elevation in a few
  degrees' steps, plus a near camera's eye in half-metre steps.
- Lowering some walls and not others bares what their full height covered: the end of a
  standing wall in line, the side of a standing post beside a lowered wall. Spawn those faces
  at load, hidden, and show them while the wall stands and its neighbour is lowered. Give each
  post side the finish of the two tiles it faces, or a post in a plaster room shows its outside
  material as a dark strip.
- A door fading out with its lowered wall leaves nothing to see: give each door a low leaf at
  the stand-ins' height, shown in its place and turned with the door.
- The storeys above the player's and the roof fade while inside. Half a metre up a flight the
  storey above shows too, and on it the walls hiding the stairwell's room drop. The parts of
  wall tops under the storey above show only on the highest storey shown (walls-on-edges).
- Known limit: a third-person camera pulled in before the first collider behind the player
  stops at lowered walls too (their colliders stay), so in a small room it stands at the
  player's back. A fix would skip the colliders of walls the cutaway lowered.

## Tests
- The circle: it opens while the hiding box keeps tint alpha 1 (give the box the fade
  component, so an old whole-object fade fails red); one occluder kind per fresh app when
  switches decide by kind; a part the cutaway hid does not open the circle; a building stays
  shut while the player stands outside it; one surface opens alike on both sides of the
  circle's depth (a Rust mirror of the shader's opening function); a wall behind the player
  stays shut however high it reaches. Let eased values land (about a second at 60 Hz) before
  asserting 1.0. Mutate the in-front test into a 3D depth test: the height case must fail.
- Groups: a wall in front of the player opens whole, a wall running past it whole or not at
  all, a corner post with either wall, and a thing beside the player stays.
- The cutaway: three rooms side by side and in front, the player in one, from all four views,
  listing both the walls that must drop and those that must stay; a near eye in the next room
  lowers what stands between and nothing behind it; a parallel view lowers what a perspective
  one from far away along the same way does. Mutations worth making: lines of sight followed
  past the wall's height, doors not parting rooms, an edge off by one in the walk, a post
  lowered with any of its walls instead of all, the junction faces never shown, the low leaf
  not turning.
