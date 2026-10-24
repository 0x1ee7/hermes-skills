# Engine recipes and API notes

Worked against wgpu 30.0.1, winit 0.30.13, bevy_ecs 0.20.0, gltf 1.4.1, glam 0.34 and image 0.25.
For other versions read the local source (`~/.cargo/registry/src/*/<crate>-<ver>/`) before
writing calls.

## Testing without a GPU

- WGSL: parse and validate every shader in a unit test. wgpu re-exports naga, so there is no
  new dependency:

  ```rust
  use wgpu::naga;

  fn validate(source: &str) {
      let module = naga::front::wgsl::parse_str(source)
          .unwrap_or_else(|e| panic!("{}", e.emit_to_string(source)));
      naga::valid::Validator::new(
          naga::valid::ValidationFlags::all(),
          naga::valid::Capabilities::all(),
      )
      .validate(&module)
      .unwrap_or_else(|e| panic!("{}", e.emit_to_string(source)));
  }
  // validate(include_str!("shaders/mesh.wgsl"));
  ```

- Shader math: mirror the WGSL function in Rust (glam) in the test module and compare it with a
  reference formula. Also assert that the old formula is wrong for the same input, so the test
  shows what the fix changes.
- Pass logic: move sorting, batching and vertex building out of `prepare` into free functions
  over plain data. GPU readiness comes in as a predicate (`ready: impl Fn(Handle) -> bool`).
- Handles that only the asset server can create: open the server on the repo's assets dir
  (`Path::new(env!("CARGO_MANIFEST_DIR")).join("../../assets")`) and add solid-colour data.
  Don't widen constructors just for tests.
- Winding, before enabling culling: every non-degenerate triangle must satisfy
  `(pb - pa).cross(pc - pa).dot(na + nb + nc) > 0`. Keep that helper `#[cfg(test)] pub(crate)`
  next to the mesh type, so the importer tests and the generator tests share it.

## wgpu 30

- Limits: request `adapter.limits()`, not `Limits::default()`, then check what the engine needs
  and fail with a readable error. Storage buffers in vertex shaders (GPU skinning):
  `adapter.get_downlevel_capabilities().flags.contains(DownlevelFlags::VERTEX_STORAGE)` and
  `limits.max_storage_buffers_per_shader_stage >= 1`. There is no vertex-stage-only limit.
- Uncaptured validation errors panic by default. Install `device.on_uncaptured_error(..)` to log
  them instead (it takes an `Arc`ed handler; check the signature locally).
- Vsync switch: `PresentMode::AutoVsync` / `AutoNoVsync`.
- Samplers: `mipmap_filter` is `wgpu::MipmapFilterMode`. Linear min and mip filtering, with the
  texture's own `mag_filter`, keeps pixel art crisp up close and stable far away.
- `create_texture_with_data` with `TextureDataOrder::LayerMajor` takes every mip level back to
  back in one slice.
- Bind groups belong to a layout. Cache the view and sampler per texture centrally, and keep
  bind groups per pass.
- Per frame: cache `QueryState`s, reuse `Vec`s with `clear()`, and upload glam matrices with
  `bytemuck::cast_slice` (glam's `bytemuck` feature makes `Mat4` Pod).
- WGSL has no matrix `inverse()`. Normals under non-uniform scale: for the 3x3 columns a, b, c
  use `mat3x3(cross(b, c), cross(c, a), cross(a, b))` (the inverse transpose times the
  determinant). Multiply by the sign of `dot(a, cross(b, c))`, then normalise.

## winit 0.30

- Pause while hidden. Paused means minimized (`window.is_minimized() == Some(true)` or `Resized`
  to 0x0) or `WindowEvent::Occluded(true)` (not reported on Windows). While paused:
  `ControlFlow::Wait`, no `request_redraw`, no `app.update`. On resume: `ControlFlow::Poll`,
  reset the frame clock so hidden time never reaches the simulation, and request a redraw.
- Window sizes go in `LogicalSize`. Divide touchpad pixel deltas by `window.scale_factor()`.

## bevy_ecs 0.20

- `SingleThreadedExecutor::default()` sets `apply_final_deferred = false`, so commands from the
  last systems never apply; use `::new()`. For schedules of a few systems it measured ~0.5 us
  per update, against ~26 us multi-threaded.
- Ambiguity detection: call `schedule.get_build_settings()`, set
  `ambiguity_detection = LogLevel::Error`, then `set_build_settings(..)` (fine after systems are
  added). The schedule then panics in `run` with "Error when initializing schedule". A headless
  test that builds the app with the game plugin and runs one update guards the game's systems.
- Narrowing a per-frame scan to a candidate list of entities: looking each candidate up
  (`Query::get`/`get_mut`) every frame can cost more than iterating the dense query over all of
  them. Copy what the scan reads (boxes, last written values) into the list when it is
  rebuilt, and look an entity up only to write a value that changed.
- Each resource lives on an entity of its own, and `Schedules` is inserted on the first
  `update`. Tests that count entities (spawn and despawn leaks) therefore take their baseline
  after one warm-up update and compare resources separately. Otherwise every world shows one
  phantom entity.

## See-through and cutaway features (isometric visibility)

- Open or fade only what stands between the camera and the player. A cause that ignores the
  camera (a cone in the way the player faces) makes walls the player walks up to see-through and
  shows what lies behind them. Pin it: a wall a few metres ahead of the player stays solid, with
  no circle in it, in the isometric view and in third person.
- Prefer a screen-space see-through circle to fading whole occluders. Fading a whole wall, roof
  or storey to about 0.3 opens far more than hides the player, and stacked translucent walls make
  large patchy shapes. The circle is a resource (centre at the chest, radius, strength) that the
  game eases and the renderer turns into NDC once per frame; the shaders open the flagged draws
  by screen distance alone, with a soft edge.
- Decide what the circle opens on the CPU, once a frame for the whole frame, for whole things,
  and pass it as a per-vertex or per-instance flag. Never compare each fragment's depth with the
  centre's: one plane through the chest slices any surface passing beside the player (a
  straight diagonal through the circle), and with a camera looking down, the tops of walls
  behind the player land in front of that plane.
- Judge boxes, not points: a box opens while the line of sight to the camera from the circle's
  centre, or from points on rings round it (0.3 and 0.6 of the radius, at the centre's depth,
  along the camera's right and screen-up), enters it from outside (slab test; along `-forward`
  for an orthographic camera, to the eye for a perspective one), or while its footprint lies
  wholly in front of the centre on the ground plane. One point per draw fails both ways: a bus
  whose middle lies behind still hides the player with one end, and a building beside the
  player whose middle is in front opens a hole beside it. A line that starts inside a box counts
  for nothing (eaves, a crown overhead). Quick reject: when the centre's line misses the box
  grown by the outer ring's reach in every axis, every ring line misses.
- Tile walls built from per-face quads need groups: judged quad by quad, a wall running past the
  player opens face by face with straight edges at tile boundaries, and some faces open where
  the player is not hidden at all. Put every wall tile in the group of its straight row piece
  and of its column piece (tiles contiguous along the line and stacked over storeys, two or
  more along it); a group opens whole by the box round its members, a tile opens with either
  group. A straight piece is convex, so if any of it hides part of the circle, the player lies
  behind every face of it the camera sees: opening it whole never opens a wall the player
  stands in front of. Never group a whole building or an L: the parts behind the player open
  too. Three follow-ups the captures showed: a piece every tile of which runs on further
  across it is a thick wall's thickness, not a wall (no group, or it opens alone and leaves a
  hole in the wall's top); build the side of a tile against a neighbour in a group it is not
  in (normally skipped as hidden), or a wall left standing beside an opened corner shows its
  hollow inside; and draw ground under every wall tile, or an opened wall shows the empty
  background through its footprint.
- Keep "opens" consistent across kinds: if lone things (a roof) open for lying wholly in front,
  groups must too, or the roof opens and the walls under it stay, which reads as a hollow box.
- Blob shadows (soft translucent floor quads at one height) must not write depth: two that
  overlap tie on depth, rounding picks the winner per pixel, and the streaks reshuffle whenever
  the camera moves by a hair ("stuttering" shadows). Without depth writes plain alpha blending
  stacks them (dense forests go nearly black), so draw them as a mask instead: into the colour
  target's alpha channel only (write mask ALPHA, blend `min` of one minus their cover; WebGPU
  wants factors of one for min/max), with every other draw keeping that channel at 1 (clear
  alpha 1, `REPLACE` with alpha 1, `ALPHA_BLENDING` over 1 stays 1), then one screen-wide
  triangle per storey band right after its shadows: colour times dst alpha, alpha back to 1.
  Overlaps then darken like the darkest shadow. Test the blend states GPU-free with a Rust
  mirror of the fixed-function blend (factors, ops, write mask) fed the real target states.
- A write mask and a "keep" blend component guarding the same channel are one guard twice: a
  mutation of either survives. Keep the mask and make the component a plain replace.
- Open buildings (cutaway) only while the player is inside one. A proximity rule ("open the
  building within a few metres that stands between the player and the camera") flips buildings
  open as the player walks past them, for example up an outside stair beside one; outside, the
  circle shows the player through.
- Let the circle decide on its own: rays from the chest and the head to the eye against the
  occluders' boxes (slab test), never "something has faded". Skip parts a cutaway already took
  away.
- Keep whole-part fades for the cutaway alone (building parts eased to 0 or 1); one fader eases
  them and writes tint alpha only when it changes.
- Mark occluders see-through through a component requirement (`#[require(SeeThrough)]`), so
  every spawn path gets it.
- What the character itself can see (a view field through doors and windows) is a separate
  system: it hides or darkens what lies out of sight, and never fades a wall.
- Tests: the circle opens while the hiding box keeps tint alpha 1 (give the box the fade
  component, so the old whole-object fade fails red); one occluder kind per fresh app when
  switches decide by kind; a part the cutaway hid does not open the circle; a building stays
  shut while the player stands outside it; one surface opens alike on both sides of the
  circle's depth (a Rust mirror of the shader's opening function); a wall behind the player
  stays shut however high it reaches. Let eased values land (about a second at 60 Hz) before
  asserting 1.0. Mutate the in-front test into a 3D depth test: the height case must fail.
  For groups: build test walls from blocks (four sides and a top, the way the game spawns
  them) and check a wall in front of the player opens whole, a wall running past it whole or
  not at all, a corner block opens with either wall, and a thing beside the player stays.

## Fixed timestep and interpolation

- Interpolate with `a + (b - a) * t`, never glam's `lerp` (`a * (1 - t) + b * t`): the
  latter is not exact for equal ends, so a body at rest is drawn with a last-bit wobble that
  changes with each frame's alpha, and anything following it (an eased camera: same rule) shakes
  by a hair. Pixel snapping hides that from edges but not from depth: coplanar surfaces then
  flip their depth tests frame to frame. Return an unchanged rotation as is instead of slerping
  it. Test: blend a transform with itself at many alphas (a position with a long mantissa, such
  as 9.973605) and assert exact equality; for the camera, uneven frame lengths from a small
  generator and an exact-equality check on the eye after it settles.
- Clamp the frame delta once at the top of `update` and give the clamped value to both
  schedules. Keep elapsed time in f64.
- Interpolation:
  - Store the previous transform in a fixed system ordered before the first fixed set.
  - Write a visual-only interpolated transform (lerp / slerp by alpha) in a frame system ordered
    before the first frame set. The extractor prefers it.
  - Spawn and teleport with previous == current.
  - Cameras and shadows that follow an entity must read the interpolated value, or they lead it
    by up to a tick.
  - Turn the camera in a frame system, not in the fixed step.
- Tests: avoid exact multiples of the tick, because f32 rounding can lose one. At 60 Hz,
  `update(0.055)` gives 3 ticks; `update(1.0)` hits a 5-step cap and alpha resets to 0.

## Textures

- Build mips on the CPU (`image::imageops::resize`, `FilterType::Triangle`) in premultiplied
  alpha, so transparent black texels don't darken cut-out edges. 32x80 gives 7 levels ending at
  1x1.
- Ortho pixel snapping happens in the renderer, which knows the surface height. Move the eye and
  target by under one pixel along the camera's right and up axes (one pixel = view height /
  surface height).

## glTF skinned import (gltf 1.4)

- Tests build `.glb` bytes in memory (JSON chunk padded with spaces, BIN chunk padded with
  zeros) and load them with `gltf::import_slice`. POSITION accessors need `min`/`max`, or
  validation fails.
- Merge every mesh node that uses the same skin. Warn about and skip other skins.
- Keep the transforms of non-joint ancestors (Blender's `Armature`) per root joint and apply them
  when building the palette. Baked into the rest locals, they are lost as soon as a pose
  replaces the locals.
- JOINTS_0: a weighted index past the joint count is a load error; on the GPU it would read
  another instance's palette. Zero-weight slots can point at joint 0. Normalise the weights; a
  vertex with no weight follows joint 0.
- Return errors instead of asserting (cycles, dangling parents, short inverse-bind arrays), so
  the caller's fallback mesh can take over.
- Negative-determinant node transform: swap two corners of every triangle. Missing NORMAL: use
  flat normals, not +Y.
