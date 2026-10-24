# Page recipes

Coordinates are for A3 landscape (`size="A3"`, the default): W 1587.4, H 1122.5 CSS pixels,
`MARGIN` 40. The title band ends at about y 85; content runs from `p.top` (104) to `p.bottom`
(1055); the legend baseline is `p.legend_y` (1084); the footer is drawn at H - 16.

## General rules
- Draw the bottom card row first: `cards = p.cards(M, None, p.W - 2 * M, None, [...],
  bottom=p.bottom)`. Then fit the main content between `p.top` and `cards.y - 20` (matrix rows,
  lane heights). Cards are always auto-height.
- Text sizes on A3: page title 24, package names 15, box titles 11, body 9 to 10, matrix and
  table cells 10. Nothing below 8.5.
- Route edges orthogonally with explicit waypoints. Send long edges around the outside of the
  diagram (columns at x of about 70 and 1130 to 1150). Keep parallel edges at least 15 px apart.
- Arrow labels go beside a vertical segment or just above a horizontal one, 6 to 8 px off.
- Badges: at a box's top-right edge (`p.badge(box.r - 6, box.y - 10, ID, note,
  anchor="end")`), at a group's top-right (`group.r - 12, group.y + 18`, the next one at
  `+ 40`), or in a package's bottom row. Never at a group's top-left, where its label is.
- Kinds: `core` for library or engine packages, `app` for application, game or UI code, `data`
  for state, files and schemas, `platform` for OS, GPU, database or network facing parts,
  `external` for third-party code and CI, `tool` for offline scripts. Rename them for the
  project in `kit.KIND_NAMES`.

## 01 Overview: packages, dependencies, rules
- One `p.package(...)` per package, 460 x 130 to 140, in layer rows (y 104, 304, 504, 704):
  the most depended-on package at the bottom. Two columns at x 100 and 640.
- One arrow per dependency, from the user to the provider. If the project has rules about
  directions ("the game never depends on the renderer"), show a forbidden edge on the matrix
  page rather than as an arrow here.
- `stats` on the right of each node: "2,539 lines · 33 tests". External dependencies as chips;
  amber (`platform`) for those facing the OS, GPU or network.
- Right column at x 1200, width 347: reading guide, workspace/toolchain/CI (process badges),
  size, start-reading-here (four or five file paths).
- Bottom row: one card per architectural rule.

## 02 Modules and public API
- `p.panel(...)` three per row: width `(p.W - 2 * M - 2 * 16) / 3`, height
  `max(Page.panel_height(sections))` across the row, 16 px gaps. Check that the grid ends above
  y 1045.
- A section is (name, note, items, badge IDs). Items are the public types and functions
  ("AssetServer::open(root) · root() · manifest()"). A note starting with "private" greys the
  module out.
- Under the grid, one line: "Module names in colour are public; grey ones are private".

## 03 Interface matrix
- `p.matrix(M, p.top, cards.y - 24, rows=users, cols=providers, cells=..., kinds=...,
  layer=..., forbidden=...)`. Order rows from the top layer down; columns are the providers.
- A cell lists what the row uses from the column: calls, types read, contracts. The diagonal
  draws a dash. With `layer`, empty cells that would point upwards say so; the rest say
  "allowed, not used". `forbidden` cells are rose and explain the rule in two or three lines.
- Bottom cards: one per boundary kind (plugin API, extraction, keys and handles, platform).

## 04 Runtime lifecycle
- Lanes are groups stacked vertically, sharing the height above the cards:
  `lane_h = (cards.y - 20 - p.top) / len(lanes)`. Boxes 260 x 92, 300 px apart, centred in
  their lane, chained left to right.
- Hand-offs between lanes run from the box's bottom down into the gap between groups, across,
  and down onto the next box: `p.arrow((a.cx, a.b), (a.cx, gap_y), (b.cx, gap_y), (b.cx, b.y))`.
  Dash asynchronous hand-offs (queues, events).
- Nested schedules (a fixed step inside the update): a group inside the lane, with each stage's
  set or phase as the box header.
- Number steps with "1." and "2.", never circled digits.

## 05 Subsystem pipeline
- Four columns at x 40 or 60, 450, 840 and 1240: inputs (a read-only `data` group),
  processing, preparation, outputs (`platform` boxes). Horizontal arrows between columns at a
  shared y.
- A helper the subsystem calls in another package: its own box below the inputs, joined by a
  dashed violet arrow labelled "calls". Size the inputs group so the helper sits outside it.
- Bottom cards: the key concept (why the design works), cost today, gaps.

## 06 Content or data pipeline
- Four groups left to right: offline tools, files and the registry, the loader API,
  consumers (x 40, 450, 860, 1230; widths 380, 380, 340, 317).
- One arrow per producer into the files; don't fork a second arrow off a shared trunk.
- Bottom cards: rules (keys, generated files), checks (tests, CI), fallbacks, next steps.

## 07 Application layer
- Startup as a vertical numbered chain: boxes 360 x 62, 82 px apart, kind by owner (engine or
  application).
- Registered systems or handlers grouped by schedule or phase, with the set or route as each
  box's header.
- What the application creates (entities, resources, records), with their components or
  fields, in left-aligned boxes.

## 08 Improvement register
- `kit.improvement_register(p, areas, order, notes)`: area boxes with badges and counts per
  priority on the left, a "Suggested order" card with the order as a badge chain at the
  bottom left, and the full table on the right (ID, priority, where, finding, proposal).
- An area is (kind, name, [IDs]). List every package, including those with no open points, so
  the page doubles as a map.
