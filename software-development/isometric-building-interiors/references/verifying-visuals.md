# Verifying what buildings look like

## Test the condition the user sees
- Coplanar surfaces: collect the visible flat quads (tint alpha above 0) per layer and assert
  that no top of storey s overlaps a floor tile of storey s + 1 at the same height (within a
  millimetre), by more than a millimetre each way. Run it in every state: outside, inside with
  the storey above hidden, upstairs.
- Windows: read the window textures the game loads and assert the layout: the inside face's
  opening all clear (alpha 0), every outer face's glass over more than half of the same box,
  no hole in it, the box symmetric about the texture's middle.
- The cutaway: the set of walls lowered from each of the four views, with the walls that must
  stay up listed as well; a near camera and a parallel one as separate tests.
- Doors: a mesh drawn where the leaf stands with the stand-in's height while the wall is
  lowered, and the same transform as the leaf after the door key.
- A face's finish: the texture and tint of the face found at a known position on each side.

## Every state
Outside and inside; each storey with the storey above shown and hidden; the four view turns;
third person; doors open and shut; buildings with and without a roof, and walls outside every
building. Name the states a fix was checked in, in the work log.

## Captures
- Put the player on a tile through a scratch copy of the assets loaded by an env var
  (`ISO_ASSET_ROOT`), with the map's spawn moved; for an upper storey, put the spawn into that
  storey's `[level N at X Y]` block, whose storey the spawn takes. `rust-game-backlog-execution`
  has `scripts/prep-probe.py` for this; `game-window-control` drives the window (keys to turn
  the view, Tab for third person, the wheel to zoom, a key to switch the view field off).
- Capture before the change, at the same spots, then after. Crop the spot from both at full
  resolution, scale 2 to 4 times with nearest-neighbour, put them side by side and ask about
  each. Thin lines vanish when a whole frame is downscaled for vision.
- Images attached to the user's message are already in context: zoom into them with `region`.

## Mutations of content
- Test helpers that open the repo's assets directly (a path from `CARGO_MANIFEST_DIR`) ignore
  the asset-root env var: mutating a scratch copy reports every mutation missed. Mutate the
  repo's file in place from a byte-for-byte backup, restore it after each run, and `cmp` every
  file at the end.
- Write mutation entries for code after `cargo fmt`: rustfmt rewraps long conditions and
  blocks, and an entry written against the unformatted text no longer matches.
