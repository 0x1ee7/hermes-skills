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

## cpal 0.18 (audio device)

- Bumping from 0.15: `SampleRate` is a plain `u32` (no `.0`); a device's name is
  `device.description()?.name()` (`Device::name` is gone); `build_output_stream` takes its
  `StreamConfig` by value, and the type is `Copy`, so pass `*config` (clippy rejects a
  `clone`). `SampleFormat` gained more variants: match the ones the mixer converts to and
  `bail!` on the rest, never panic. `cargo update -p cpal` also drops bindgen, clang-sys and
  the Android crates from a desktop build; run `cargo deny check` and the smoke run with the
  device on (`audio: <name> at <rate> Hz, <n> channels`) and off (`ISO_AUDIO=0`).

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
- `Query<&mut T>` iterates as `Mut<T>` alone; add `Entity` to the query
  (`Query<(Entity, &mut T)>`) when the system needs ids, and its `get_mut` then returns
  `(Entity, Mut<T>)`. A second query to fetch the entity conflicts with the first.

## Floor shadows

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

## Isometric buildings

Walls on tile edges, the cutaway, the see-through circle, the view field, doors and
windows of glass, with their tests and captures: the skill `isometric-building-interiors`.

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
