---
name: game-camera-from-screenshot
description: "Use when matching a game camera from a screenshot."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [gamedev, camera, fov, isometric, vanishing-points, opencv, unity, unreal, godot, blender]
    related_skills: [game-window-control, level-recipes]
---

# Game camera from a screenshot

Recovers projection type, vertical/horizontal FOV, pitch, roll, yaw relative to a level axis, and camera distance from ONE screenshot via vanishing points, then maps them to engine settings. Script: `scripts/cam_from_screenshot.py` (subcommands `detect` -> `fit` -> `scale`; outputs land in the cwd).

## When to Use

- The user wants to reproduce another game's camera (FOV, angle, zoom) from a screenshot or video frame.
- A level/asset must be framed like reference art, or a top-down/isometric camera must be matched.
- Not for pure 2D/pixel-art games without perspective cues: there the answer is just tile ratio (e.g. 2:1 dimetric).

## Setup

System Pythons may lack numpy/cv2. Make a throwaway venv in the Hermes scratch dir (git-bash `TMPDIR` can point at /tmp, so use the scratch path explicitly):

    uv venv -q --python 3.12 .venv
    uv pip install -q --python .venv/Scripts/python.exe numpy opencv-python-headless

## Workflow

1. `detect IMG` -> numbered LSD segments in `crop_{tl,tr,bl,br}.png` plus a listing with angles. View the crops and pick segment IDs.
2. V set = world-plumb edges: railing posts, columns, hanging ropes, barrel silhouettes. Exclude truss diagonals, characters, shadows.
3. B set = ONE horizontal world axis with edges on BOTH sides of the frame (e.g. left railing + right parapet). `--b-range LO:HI` around the dominant peak of the angle listing works; RANSAC drops strays.
4. `fit IMG --v ids --b-range LO:HI` -> f, vFOV, hFOV, pitch, roll, yaw-vs-axis, bootstrap 90% CI, `overlay_grid.png`, `fit.json`.
5. Accept the fit only if roll is ~0, nearly all V segments are inliers, and in `overlay_grid.png` the green grid stays parallel to the axis edges across the whole frame and the red fan matches the lean of posts.
6. Cross-check pitch independently: a horizontal circle (drum top, tire) has minor/major ~= sin(depression of its view ray). Measure it in pixels.
7. `scale IMG --obj u,v_foot,v_head,1.8 ...` (several characters) -> camera height, focus distance D, ground footprint, ortho half-size. Report the spread.
8. Round to designer-plausible values (e.g. vFOV 17, pitch 45, yaw 45) and confirm the rounded camera reprojects the edges no worse than the raw fit.

## Formulas (principal point p = image centre)

- f^2 = -(v_vert - p).(v_axis - p); vFOV = 2*atan(H/2f); hFOV = 2*atan(W/2f)
- pitch below horizon = atan2(f, |v_vert - p|); roll from the x-offset of v_vert
- yaw vs axis = atan(x_axis*cos(pitch)/f), x_axis = axis-VP x-offset after un-rolling
- full-frame equivalent focal (36 mm wide, horizontal fit) = 18 / tan(hFOV/2)
- upright pole of height h at depth D spans ~ f*h*cos(pitch)/D px; ortho half-height = (H/2)*D/f

## Engine conventions

- Unity: `Camera.fieldOfView` is VERTICAL. `Quaternion.Euler(pitch, yaw, 0)` (+pitch looks down); position = focus - rot*forward*D.
- Unreal: `FieldOfView` is HORIZONTAL (default Maintain X-Axis FOV); units are cm; `FRotator(-pitch, yaw, 0)`; SpringArm `TargetArmLength = D*100`.
- Godot 4: `Camera3D.fov` is VERTICAL with the default `keep_aspect = KEEP_HEIGHT`; camera looks down -Z; `rotation_degrees.x = -pitch`.
- Blender: `lens` in mm with `sensor_width = 36`, `sensor_fit = 'HORIZONTAL'`; rotation X = 90 - pitch.

## Applying it to an engine you own

- Keep zoom as the view height at the focus and derive the distance: D = h / (2 tan(vFOV/2)). The same number is the ortho view height, so wheel code and clamps keep working (41.5 m at 17 deg is h = 12.4 m). Scale D by the game's character height (D ~ 23 x height).
- Put near and far in proportion to D (D/8 and 8 D): zooming then keeps depth precision. At 45 deg / 17 deg the farthest ground in view lies ~1.2 D deep.
- Pin the look with a unit test against the measured numbers, then mutation-check each constant. Check three things: upright edges meet f cot(pitch) px below the centre at the reference height (f = (H/2) / tan(vFOV/2)); the two grid axes through the centre have mirrored screen slopes (45 deg yaw, no roll); and the ground widths along the bottom, middle and top rows, from the ground-pick ray.
- Prove that the renderer draws what the maths says. Project known world edges (street borders, building corners) with the camera formulas over a capture of the new build. They must sit on the edges in the picture.
- Capture before/after from the same spots: copy the old binary aside before editing, then tile each pair side by side (skill `game-window-control`).

## Lessons

- Never derive VPs from eyeballed pixel coordinates: at ~45 deg yaw the horizontal VPs sit thousands of px off-screen and a 1 deg slope error moves them enormously. Use sub-pixel LSD segments + RANSAC.
- Run CLAHE before LSD on dark game frames, otherwise most structural edges are missed.
- Pair the vertical VP (nearest, best conditioned) with the best-populated horizontal family; the two horizontal VPs alone are poorly conditioned.
- Measure small props from channel-excess printouts (e.g. G - max(R,B) for a green drum) rather than vision estimates.
- Scale is only as good as the assumed size: art-scaled props can disagree with characters by ~20%. Prefer several characters and quote the range.
- Treat the recovered distance as one zoom level; many tactics games zoom by changing distance (sometimes pitch too).
- Switching ortho to perspective breaks floor picking quietly: a slanting ray meets the plane a hair off (~2e-6 m), and `floor(y / storey_height)` puts the tile on the storey below. Set the picked point's y to the plane height exactly.
- A steeper pitch hides less. Occlusion tests and level "hide behind this" spots built for the old angle fail, or pass without checking anything. Sweep the real level with the old and the new camera (print a tile map of who hides the player), move or grow the test geometry, and mutation-check the tests that assert "stays shut".
- Pixel snapping only works for ortho. A perspective camera brings back texel crawl while it moves, and still captures cannot show that: ask the user to watch it in motion.
