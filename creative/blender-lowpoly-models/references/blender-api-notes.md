# Blender 5.2 notes for scripted low-poly models

Checked against Blender 5.2.2 LTS in `--background --factory-startup` mode.

## Scene and data
- Fresh state per model: `bpy.ops.wm.read_factory_settings(use_empty=True)` (no cube, camera,
  light, leftover materials).
- New materials come with a node tree (Principled BSDF + output). `Material.use_nodes` is
  deprecated (removal planned for 6.0); do not set it. Set both
  `bsdf.inputs["Base Color"].default_value` (linear RGBA) and `mat.diffuse_color`.
- Convert sRGB hex to linear before assigning: glTF `baseColorFactor` is linear.

## bmesh primitives
- `bmesh.ops.create_cube(bm, size=1.0, matrix=M, calc_uvs=False)` returns `{"verts"}`; scale
  through the matrix.
- `bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=n, radius1, radius2,
  depth, matrix)`: centred on its origin along local Z. With `radius2=0` build the cone by hand
  (a ring and an apex) to avoid degenerate caps.
- `bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0, matrix=M)`: `subdivisions=1` is
  the 12-vertex icosahedron (20 faces); 0 behaves the same; 2 gives 80 faces.
- Material per face: `face.material_index`; flat: `face.smooth = False`.
- Rigid skinning: `dl = bm.verts.layers.deform.verify()`, `v[dl][group_index] = 1.0`; create
  the object's vertex groups in the same order as the indices.
- Finish with `bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])` (closed parts only).
- Flat bottom for sunk shapes: `bmesh.ops.bisect_plane(..., plane_co=(0,0,0),
  plane_no=(0,0,1), clear_inner=True)` then `bmesh.ops.holes_fill(bm, edges=<cut edges>,
  sides=0)`.

## Armatures
- Edit bones need edit mode: set the armature object active, `bpy.ops.object.mode_set(mode=
  "EDIT")`, add `edit_bones.new(name)` with `head`, `tail = head + (0, 0, 0.1)`, `roll = 0`.
- Bones pointing straight up with roll 0 export with **no rotation** in glTF (translations
  only), the same as a hand-made rig with identity joints.
- Mesh parented to the armature plus an `ARMATURE` modifier exports as a skin; the armature
  object becomes a non-joint parent node (the engine keeps it as `parent_offset`).

## glTF export settings that matter
`bpy.ops.export_scene.gltf(filepath, export_format="GLB", use_selection=True, export_yup=True,
export_apply=True, export_texcoords=False, export_normals=False, export_tangents=False,
export_materials="EXPORT", export_vertex_color="NONE", export_attributes=False,
export_cameras=False, export_lights=False, export_extras=False, export_animations=False,
export_morph=False, export_skins=<rigged>, export_def_bones=False, export_leaf_bone=False,
export_rest_position_armature=True, export_influence_nb=4, export_image_format="NONE")`
- `export_apply=True` applies modifiers except the armature, so skins survive.
- `export_format`'s enum items are dynamic; pass `"GLB"`.
- List every property with
  `bpy.ops.export_scene.gltf.get_rna_type().properties` before trusting memory.
- Output is byte-identical between runs of the same Blender version.

## Preview renders (contact sheets)
- Workbench renders headless: `scene.render.engine = "BLENDER_WORKBENCH"`,
  `display.shading.light = "STUDIO"`, `color_type = "MATERIAL"`; give the scene a world with a
  mid-grey colour or the background is black.
- Re-import the exported `.glb` files to render them (`bpy.ops.import_scene.gltf`): that also
  proves the files load.
- Orthographic camera from the game's angle: direction `(cos e/sqrt2, -cos e/sqrt2, sin e)`
  with e = 30 degrees; fit `ortho_scale` to the projected bounds.
