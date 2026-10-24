# Markdown explainer with Mermaid diagrams

For "explain how subsystem X works, with diagrams", when an engineer must understand it and fix
small bugs: one Markdown file in the project's docs folder. Mermaid draws the flows and data
structures; fenced ASCII draws the geometry. It renders on GitHub and in VS Code, diffs like
code and needs no build step. Whole-codebase overviews are the PDF page set (SKILL.md).

## Procedure
1. Read the subsystem's code end to end before writing: the deciding side, the shared types, the
   output side down to shaders or queries. Take the run order from where it is registered (a
   chained system set, a middleware list), never from file names. Note every entry point and
   constant with `file:line`.
2. Write the sections in this order:
   - what it does and how to try it (command, level, keys);
   - the big picture: the layers, and a table of the types they share (defined in, written by,
     meaning);
   - one frame or request step by step: a pipeline diagram plus a table (step, reads, writes,
     writes when);
   - the central idea or data model: the core struct as a short excerpt, and a diagram of how
     its parts combine;
   - what is set up once (load, startup) and what is decided per frame or request: a table;
   - one section per mechanism, each with its decision chart or geometry sketch;
   - the output path (rendering, serialisation): its order and styles as a diagram and a table;
   - tuning knobs: every constant, its value, `file:line`;
   - a field guide: symptom, where to look, what to check (a table); known quirks found while
     reading the code, each with its mechanism; how to reproduce, pin in a test, and verify;
   - extending it: a new cause, a new type, a new style.
3. Name the commit the line numbers belong to; they drift. Run
   `python scripts/check_refs.py <doc.md> <repo root>` and read each printed line: it must be
   the declaration or constant the text names.
4. State a quirk as what the code does ("sprites write depth even where translucent, so ..."),
   and say it was found by reading when nobody saw it on screen. Text the user supplies for the
   doc: keep its structure and wording, check each claim against the code, add `file:line`
   references and a sketch, and say what you added.
5. Validate the diagrams (below), then check every number and condition in the text against the
   code once more.
6. Link the doc from the main architecture doc in one line. Commit only when asked.

## Mermaid that parses and reads well
- Quote every label: `id["text"]`, decisions `id{"text"}`; break lines with `<br/>`.
- Never name a node `end` (it closes a subgraph); keep subgraph ids apart from node ids.
- classDiagram: generics as `Vec~T~`; no brackets or semicolons inside members (write
  `bool per quadrant`, not `[bool; 4]`).
- Mermaid wraps label lines at about 200 px: keep each `<br/>` segment under about 25
  characters, or it breaks them mid-phrase.
- A node that feeds most others (a settings resource) crosses every other edge: drop those
  edges and say "read by the steps below" in its label.
- A node holding a list is unreadable: end the chart with "write X (list below)" and put the
  list in the text under it.
- Number the steps of a long chain in their labels ("3 cutaway"), so the order survives any
  layout.
- Geometry (compass sectors, grid neighbourhoods, before and after tile plans, chunk selection)
  reads better as fenced ASCII than as Mermaid.

## Validate by rendering
- Fetch mermaid.js once into scratch:
  `curl -sSL -o <scratch>/mermaid.min.js https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js`.
- `python scripts/render_mermaid.py <doc.md> <out dir> <scratch>/mermaid.min.js [width height]`
  renders every block in headless Edge or Chrome, prints OK or the parse error per diagram and
  saves a PNG of each; it exits 1 when one fails to parse.
- Look at every PNG with `vision_analyze` ("list concrete layout defects"). Give tall charts a
  taller window (the last two arguments) so nothing is cut off; fix and re-render until clean.

## Keeping it current
- When the code it explains changes, update the doc in the same change. Grep it for every
  symbol and word of what changed (functions, fields, constants, keys, settings) and fix each
  place: diagram nodes and edges, tables, the constants table, the field guide, the quirks.
- When a part is removed, keep a short "Removed: X, and why" section with the test that guards
  against its return, instead of deleting the history without a trace.
- Re-run `check_refs.py` and `render_mermaid.py` before committing: removed nodes leave
  dangling edges, and line numbers shift in every file the change touched.
- Take new line numbers from `grep -n` once the code is final, then edit the doc: numbers
  written into an edit script while the code still changes are wrong in every edited file. Fix
  them with one `sed` per doc and run `check_refs.py` again until every line matches.
