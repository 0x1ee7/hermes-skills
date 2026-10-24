# PDF export with headless Chromium

`diagram_kit.build()` implements all of this. Read it when changing the kit or when a print
comes out wrong.

## Page setup
- One SVG per page in CSS pixels: A3 landscape is 1587.4 x 1122.5 (`mm * 96 / 25.4`), A4
  landscape 1122.5 x 793.7. Title, cards, legend and footer go inside the SVG, so every label
  passes the same fit checks.
- HTML wrapper: `@page { size: 420mm 297mm; margin: 0; }` and `html, body { margin: 0; height:
  297mm; overflow: hidden; background: #020617; -webkit-print-color-adjust: exact;
  print-color-adjust: exact; }`, with `svg { width: 420mm; height: 297mm; }`. Without
  print-color-adjust the dark background does not print; the fixed height with
  `overflow: hidden` prevents a second, blank page.
- Fonts: installed families only. Google Fonts need the network and may load after printing
  has started.

## Print
```
msedge (or chrome) --headless --disable-gpu --no-first-run --no-default-browser-check
    --no-pdf-header-footer --print-to-pdf-no-header --user-data-dir=<temp dir>
    --print-to-pdf=<out.pdf> <file URI of the HTML page>
```
- Verified with Edge 155 on Windows: the CSS page size is honoured, so the PDF is exactly A3.
- A throwaway `--user-data-dir` keeps the user's profile out and works while the browser is
  open. Clean it up with `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)`: browser
  helpers can hold files for a moment after exit.
- Stderr chatter ("Edge LLM: catalog update failed") is harmless. Trust the exit code and the
  file.
- The HTML `<title>` becomes the PDF's Title.

## Deterministic bytes
Skia's output differs between runs only in `/CreationDate (D:YYYYMMDDHHmmSS...` and
`/ModDate`. Replace those 14 digits with a fixed time: same length, so the cross-reference
offsets stay valid. The kit uses `SOURCE_DATE_EPOCH` when set, else the last commit's time,
else the generator file's modification time (outside git, `now()` would change every build).
Rebuilding the same source with the same browser then gives identical sha256 sums; another
browser version may still change bytes.

## Checks after printing
- Count `/Type /Page` objects (not `/Pages`): one per diagram.
- Embedded fonts should all be the main family. Seen falling back on Windows 11: circled
  digits (Cambria Math), `⇄` (Consolas), `⚠` and `★` (Segoe UI Symbol). Safe in JetBrains Mono:
  `→ ← ↓ ↑ · • ● ○ × ✓ ≤ ≥ … ° ▶ ◆ — Σ α`.
- Width calibration: JetBrains Mono advances exactly 0.6 em, so 100 "M" at 20 px span 1200 px.

## Review loop
- `review_pdfs.py <dir> --out <review dir>` renders A3 at 1906 x 1348 (scale 1.6).
- `vision_analyze` each PNG with a request for concrete defects: overlapping text, text
  crossing borders, arrows through text or ending in odd places, empty or unbalanced areas,
  clipping.
- Zoom into dense parts with `region=[x1, y1, x2, y2]` in original pixels: tables, matrices,
  card columns, badge rows.
- Rebuild one page with `--only NN` while fixing it, then rebuild all and review all once more.
