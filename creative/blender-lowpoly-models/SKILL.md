---
name: blender-lowpoly-models
description: "Use when building low-poly glTF models with Blender."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [blender, gltf, low-poly, 3d-models, game-assets, rigging, mcp, bmesh]
    related_skills: [rust-game-backlog-execution]
---

# Low-poly game models with Blender

Build flat-coloured low-poly models (buildings, vehicles, props, rigged animals, plants) as
glTF from Python builders run in headless Blender, so every model is reproducible, small and
checked by tests. A live Blender driven through MCP is for sketching and looking only; what you
keep goes into a builder. Worked out on the iso-engine repo (`tools/blender/`, Blender 5.2 LTS);
the kit carries over to any engine that loads glTF.

## When to Use
- Add, vary or fix 3D models for a game: props, buildings, vehicles, animals, vegetation.
- Look at or tweak a model interactively in a running Blender (`mcp_blender_*` tools).
- Don't use for: sculpted or textured PBR art, or third-party assets (licence first).

## Prerequisites
- `blender --version` reports the pinned version (iso-engine: 5.2.x). A portable zip in the
  user profile needs no admin rights; the winget package is a per-machine MSI (UAC prompt).
- Pillow for screenshots and diffs without a global install:
  `uv run --no-project --with pillow python script.py`.
- Optional: `gltf-transform validate` (npm `@gltf-transform/cli`).
- Optional MCP: `uv tool install mcp-for-blender`, `mcp-for-blender install-addon`, enable the
  addon and save preferences in a `blender --background --python-expr` run, then
  `hermes mcp add blender --command <absolute path to mcp-for-blender.exe> --env
  DISABLE_TELEMETRY=true` (answer `Y` on stdin). Tools appear in sessions started afterwards.

## How to Run (iso-engine)

```
terminal(command="blender --background --factory-startup --python tools/blender/build_models.py -- --only 'prop.*' --previews <scratch>/previews", timeout=600)
```

`--list` keys and files, `--manifest` prints manifest lines, `--out DIR` builds elsewhere (to
compare bytes), `--previews DIR` renders one contact sheet per family from the exported files.
Delete `tools/blender/__pycache__` afterwards (or keep it gitignored).

## Procedure: add a model
1. Choose the key's family (`tree`, `deco`, `prop`, `building`, `vehicle`, `animal`, ...): in
   iso-engine it decides collision, shadow and behaviour (references/iso-engine-conventions.md).
   Done when the key is picked.
2. Write a builder in `tools/blender/models_<family>.py` with `@model(key, path, **params)`;
   stack decorators for colour or size variants. Done when `--list` shows the key.
3. Build it alone with `--previews`; open the sheet with `vision_analyze`, then zoom with
   `region` on the full-size image. Done when the build prints no warning and every part sits
   where it should (heads forward, wheels on the ground, roofs on walls).
4. Add the `--manifest` line to `assets/manifest.ron`; run `cargo test -p engine_assets`
   (stands on y = 0, origin inside footprint, outward faces, identity rest pose, no orphans).
5. Place it: an `[objects]` line or a `[scatter]` letter in the map; clear scatter letters
   under its footprint (scripts in references/map-editing.md). Done when the map tests pass.
6. Look at it in game: `scripts/vantage.sh` moves the spawn and zoom temporarily, captures with
   `scripts/capture.ps1` and restores both files. Done when `git diff` shows no leftovers.
7. Prove reproducibility: build into two `--out` dirs, `sha256sum` against `assets/models`;
   `gltf-transform validate` each new file. Done when the hashes match.
8. Commit modularly, each commit passing the gates on its own: kit or build-script changes
   first (rebuild everything and show no model changed); then the family (builder, generated
   files, manifest keys); then its placement in the map; game code such as a new behaviour in
   its own commit, after the models its tests use. Never mix map edits into a model commit.
9. Close the item with a commit that changes no asset: tick it in the work queue, end its
   work-log line with `Commits: <the item's other hashes>`, and refresh the asset list
   (`python3 tools/list_assets.py`, then `--check` must print "current"). Done when
   `docs/asset-list.md` cites the new models' commits.

## Modelling rules
- Blender axes: metres, Z up, **front -Y**, left +X; origin at the footprint centre on z = 0.
- Only closed primitives (`box`, `cylinder`, `cone`, `sphere`, `profile`): the engine culls
  back faces, so a sheet seen from both sides must be a thin box.
- `profile(points, depth, at, axis)`: axis X takes (y, z) points, Y takes (x, z), Z a plan
  (x, y) extruded upwards. Gables, gambrels, awnings, wedges, boat hulls.
- `rot` is XYZ Euler degrees about the part's centre. A positive X turn tips a part's top
  towards -Y (forwards): necks lean out with +X, tails lean back with -X.
- A cone or cylinder with `axis="Y"` points its +end to -Y (forwards): beaks need no extra turn.
- Icosphere `subdiv=1` is the bare 20-face icosahedron (rocks, berries); 2 is 80 faces (crowns).
- Wheeled models end with `m.settle()`; sunk shapes (rocks, tufts) with `m.cut_ground()`.
- Scale details for the camera, not for life: at ~65 px per metre a 5 cm flower head is a dot.
- Rigs: `m.bone(name, head, parent)` before the parts bound to it; bones point straight up
  with no roll, so the exported rest rotations are identity and gameplay can turn joints about
  model axes. Bind each primitive to exactly one bone (rigid skinning).
- Variants (snowy, recoloured, bigger): add builder parameters whose defaults reproduce the old
  model exactly: same primitives in the same order, no extra `rng` draws on the default path,
  extra parts only under `if param:`. A size factor `s` multiplying every literal is exact at
  1.0. Prove it with a full rebuild compared by hash against `assets/models`.

## Pitfalls
- `--factory-startup` is mandatory: user preferences and addons (MCP for Blender) otherwise leak
  into the export.
- Another Blender version can change bytes: rebuild only the keys you changed (`--only`) and
  restore the rest with git.
- `Material.use_nodes` is deprecated in 5.x; new materials already have a Principled BSDF.
- Leave normals out of the export: glTF shades a mesh without NORMAL flat (spec), Blender and
  the engine follow it, and files shrink 4-5x. Keep a signed-volume test for inside-out meshes.
- Previews: text labels have no bounds until `bpy.context.view_layer.update()`; compute camera
  axes from the rotation quaternion, not `matrix_world` (stale before a depsgraph update).
- One-off map scripts: anchor section matches to whole lines (`"\n[scatter]\n"`); a header
  comment that mentions `[scatter]` once ate the whole grid. Back the map up before each run.
- Tall models on the map edges nearest the default camera hide everything behind them; keep
  forests on the far edges and low clutter on the near ones.
- A family's contact sheet shrinks new models to a few pixels; preview only the new keys:
  `--only key1 --only key2 --out <scratch> --previews <scratch>` (the `--out` keeps
  `assets/models` untouched), then zoom with `region`.
- Levels built from many models: see the `level-recipes` skill (generator, seasons, captures).
- MCP's addon refuses to serve in `blender --background`; `look` works with the window
  minimized. The socket has no auth: localhost only, close Blender when done.
- Windows shell: background jobs (and foreground timeouts over 600 s) lose exported variables,
  so `$SCRATCH`-style paths become `/` and files land in the git-bash root. Spell paths out.

## Verification
- The build prints no `warning:` line; contact sheets and an in-game capture were looked at.
- `cargo test --workspace` passes, including the manifest-wide model conventions.
- Two builds give identical `sha256sum` output; `gltf-transform validate` reports nothing.
- Screenshots for docs: `scripts/quantize.py` (octree, no dither); check small saturated
  details (a character's shirt) survived, median-cut quantizing greyed them out.

## Files
- `references/iso-engine-conventions.md`: families, map format, rig joint names, colliders.
- `references/blender-api-notes.md`: Blender 5.2 bmesh, exporter and preview facts.
- `references/map-editing.md`: editing the text map with one-off scripts safely.
- `scripts/capture.ps1`, `scripts/vantage.sh`, `scripts/diff.py`, `scripts/quantize.py`,
  `scripts/mcp_smoke.py`.
