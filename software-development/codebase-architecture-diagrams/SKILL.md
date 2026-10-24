---
name: codebase-architecture-diagrams
description: "Use when documenting codebase architecture with diagrams."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [architecture, diagrams, codebase-analysis, documentation, svg, pdf]
    related_skills: [architecture-diagram, codebase-inspection, rust-workspace-review, pdf]
---

# Codebase Architecture Diagrams

Analyse a repository, then draw a set of architecture diagrams as PDF: packages and their
dependencies, modules and public API, interfaces between packages, runtime and data pipelines,
and improvement points, marked as badges on every page and listed in a register on the last.
Pages are laid out by a project-local Python generator built on `scripts/diagram_kit.py`
(standard library, measures every label) and printed by headless Edge or Chrome. The look is
the dark design system of `architecture-diagram`.

An explainer of one subsystem, for the engineers who change and debug it, is a Markdown file
with Mermaid and ASCII diagrams instead: see `references/markdown-mermaid.md`.

## When to Use
- "Make architecture diagrams of the codebase", "identify modules and interfaces", "highlight
  improvement points", especially as PDF or for a docs folder.
- Refreshing such a set after the architecture changed: update the generator, rebuild, review.
- "Explain how subsystem X works, with diagrams", for someone who will fix or extend it: the
  Markdown explainer (`references/markdown-mermaid.md`, checked with `scripts/render_mermaid.py`).
- Don't use for: one quick diagram or a single HTML page (`architecture-diagram`); cloud or
  infrastructure topology with no code to analyse (`architecture-diagram`).

## Prerequisites
- Python 3.10+; the kit and generators use the standard library only.
- Edge or Chrome. The kit finds the usual install paths; otherwise set `CHROME=/path/to/it`.
- A monospace font: JetBrains Mono (widths are calibrated to its 0.6 em advance). Cascadia
  Mono and Consolas are narrower, so the fit checks still hold with them.
- Review only: `pypdf`, `pypdfium2`, `pillow` in a scratch venv, for example
  `terminal(command="python -m venv <scratch>/venv && <scratch>/venv/Scripts/python -m pip install pypdf pypdfium2 pillow")`
  (`bin/` instead of `Scripts/` on Linux and macOS).

## Files
- `scripts/diagram_kit.py`: the kit. `Page` primitives (rect, text with `fit=`, arrow),
  components (box, group, chip, badge, card, cards, legend), composites (package, panel,
  matrix), `improvement_register`, and `build`/`main` (layout, print, date pinning, one-page
  check). Its docstrings are the API reference.
- `scripts/review_pdfs.py`: page count, size, fonts and title of each PDF, plus a PNG per page;
  exits 1 on a font fallback or an unexpected page count.
- `templates/example_diagrams.py`: a four-page generator for a fictional web shop (overview,
  request lifecycle, interface matrix, register). Start a project's generator from it.
- `references/analysis.md`: what to collect for each page and how; the improvement register.
- `references/page-recipes.md`: layouts and coordinates for the standard pages.
- `references/pdf-export.md`: page setup, print flags, deterministic bytes, review loop.
- `references/markdown-mermaid.md`: the subsystem explainer: sections, Mermaid rules that keep
  diagrams parsing and legible, validation.
- `scripts/render_mermaid.py`: renders each Mermaid block of a Markdown file in headless Edge or
  Chrome; prints OK or the parse error per diagram and saves a PNG each.
- `scripts/check_refs.py`: prints every `file:line` reference of a Markdown file next to the
  line it points at; exits 1 on a missing file or a line past the end.

## Procedure
1. Analyse the repository (`references/analysis.md`). Read docs, contributor rules, manifests,
   CI, and every source file of a small repo. Write down the facts each planned page needs and
   every improvement point (ID, priority, where, finding, proposal, short). Done when every
   number has a command behind it and every finding is marked verified or code-read.
2. Plan the pages. Start from the standard eight (`references/page-recipes.md`): overview,
   modules and API, interface matrix, runtime lifecycle, key subsystem pipeline, content or
   data pipeline, application layer, improvement register. Drop or rename what does not apply
   (a web service might get request lifecycle, data model, deployment). Done when each page
   has a one-line purpose.
3. Set up the generator in the project: copy `scripts/diagram_kit.py` next to the project's
   tools (e.g. `tools/diagram_kit.py`), or inline it into the generator if the project prefers
   single-file tools. Start `tools/architecture_diagrams.py` from
   `templates/example_diagrams.py`: register the improvement points, write one draw function
   per page, list them in `SPECS`, and call `kit.main(SPECS, "docs/architecture", project=...,
   generator=..., root=<repo root>)`. Copy, never import from the skill folder: the project
   must rebuild without the skill.
4. Draw page by page, iterating with `--only NN`. Pass `fit=` for any free text inside a
   container; the kit's components do it themselves. Done when a full run writes every PDF
   without a `layout error:` line.
5. Review: run `scripts/review_pdfs.py docs/architecture --out <scratch>/review` with the venv
   Python, then `vision_analyze` every PNG ("list concrete layout defects"), and zoom into
   dense regions (tables, matrices, card columns, badge rows) with `region`. Fix, rebuild,
   re-review. Done when a full pass finds no defect.
6. Deliver: `docs/architecture/README.md` (one line per PDF, the badge colours, the rebuild
   command, a note that pages are drawn from reading the code), a one-line link from the main
   architecture doc, and the generator plus kit in the project's tools. Run the project's other
   doc checkers so the new files break nothing. Commit only when asked.

## Quick Reference
```
python tools/architecture_diagrams.py                 # every page
python tools/architecture_diagrams.py --only 04       # one page, by number or name
python tools/architecture_diagrams.py --html <dir>    # keep the HTML pages for debugging
python tools/architecture_diagrams.py --list          # page numbers and names
<venv python> <skill dir>/scripts/review_pdfs.py docs/architecture --out <scratch>/review
```
Kit, most used: `p.package(...)` overview node; `p.panel(...)` and `Page.panel_height(...)`
module panels; `p.matrix(...)` interface matrix; `p.box(...)`, `p.group(...)`,
`p.arrow(*points, label=...)`; `p.cards(..., bottom=p.bottom)` auto-height card row;
`p.badge(x, y, "N-03", "note", anchor="end")`; `p.legend(kit.MARGIN, p.legend_y, kinds)`;
`kit.improvement_register(p, areas, order, notes)`. Content runs from `p.top` to `p.bottom`.

## Pitfalls
- Glyph fallback: circled digits, `⇄`, `⚠` and `★` come from other fonts (Cambria Math,
  Consolas, Segoe UI Symbol). review_pdfs.py flags them; write "1.", "2.", "/" or words.
- Size cards to their content (`h=None`) and anchor the bottom row (`bottom=p.bottom`), then let
  the main content fill what is left. Hand-picked heights leave cards half empty.
- Text that looks fine in code is illegible on the page: keep matrix and table cells at 10 px on
  A3 and nothing below 8.5 px.
- Two parallel arrows closer than about 15 px read as one bus. Drop the redundant edge rather
  than nudging it.
- Badges at a group's top-left collide with the group's label; anchor them at the right edge.
- A box drawn inside a dashed group reads as part of it; shrink the group or move the box.
- Free-floating words ("uses") confuse; label edges through `arrow(label=...)`, which also
  masks the line behind the text.
- Numbers go stale: take them from commands, name the commit in the footer (the kit does), and
  say in the README that the pages are drawn from reading the code.
- The fit checks assume a monospace font. With another font, recalibrate `kit.ADVANCE` (print
  100 "M" at 20 px next to a 1200 px line and compare).
- Windows: git refuses repositories on drives without ownership ("dubious ownership"); the kit
  passes `-c safe.directory=<root>`. Edge's stderr chatter ("Edge LLM: catalog update
  failed") is harmless.
- The system Python may have no packages, or pip may belong to another interpreter. The kit
  needs none; the review libraries go into a scratch venv.
- Pyright cannot resolve a kit added to `sys.path` at run time: keep the kit next to the
  generator or add `# pyright: ignore[reportMissingImports]` to the import.
- An A3 page with embedded font subsets is 80 to 140 KB; eight pages come to about 1 MB.
  Say so before adding them to a repository that watches its size.
- The dark background prints heavily. If the user prints, offer a light variant: swap `BG`,
  `UNDERLAY`, `WHITE`, `TEXT` and the `KINDS` fills.

## Verification
- The generator exits 0 and writes one PDF per page; `layout error:` never appears.
- review_pdfs.py: every PDF has 1 page of 420x297 mm (A3) and only the main font; 0 problems.
- Rebuilding the same source gives identical sha256 sums: the kit pins the PDF dates
  (`SOURCE_DATE_EPOCH`, else the last commit, else the generator's modification time).
- Every page passed a full-page `vision_analyze` look, and dense regions a zoomed one.
- Every improvement ID is in the register and on at least one other page; every package with
  open points shows its badges on the overview.
- The generator compiles (`python -m py_compile`) and meets the project's style (line length,
  type checker when available).
- `docs/architecture/README.md` lists every PDF, and the main architecture doc links to it.
