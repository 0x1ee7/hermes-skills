#!/usr/bin/env python3
"""Check PDF diagrams and render them to PNG for review.

    python review_pdfs.py docs/architecture              # every PDF in a folder
    python review_pdfs.py a.pdf b.pdf --out review --scale 1.6

For each PDF it prints the page count, page size, title and embedded fonts, and renders every
page to PNG in --out (default: diagram-review in the system temp folder) for vision review.
Exits 1 when a PDF does not have --pages pages, or embeds a font whose name lacks --font: a
glyph the main font does not have fell back to another font, so replace that glyph.

Needs pypdf, pypdfium2 and pillow (python -m pip install pypdf pypdfium2 pillow); install
them in a scratch virtual environment to keep the system Python clean.
"""

import argparse
import sys
import tempfile
from pathlib import Path

try:
    import pypdf
    import pypdfium2 as pdfium
except ImportError:
    sys.exit("needs pypdf, pypdfium2 and pillow: python -m pip install pypdf pypdfium2 pillow")


def fonts_of(reader):
    names = set()
    for page in reader.pages:
        resources = page.get("/Resources") or {}
        for _, font in (resources.get("/Font") or {}).items():
            names.add(str(font.get_object().get("/BaseFont", "?")).split("+")[-1])
    return names


def main():
    parser = argparse.ArgumentParser(description="Check and render PDF diagrams.")
    parser.add_argument("paths", nargs="+", help="PDF files or folders of PDFs")
    parser.add_argument("--out", default=str(Path(tempfile.gettempdir()) / "diagram-review"))
    parser.add_argument("--scale", type=float, default=1.6,
                        help="pixels per PDF point (1.6 renders A3 at 1906x1348)")
    parser.add_argument("--pages", type=int, default=1, help="expected pages, 0 for any")
    parser.add_argument("--font", default="JetBrainsMono",
                        help="every embedded font name must contain this")
    args = parser.parse_args()

    pdfs = []
    for raw in args.paths:
        path = Path(raw)
        pdfs += sorted(path.glob("*.pdf")) if path.is_dir() else [path]
    if not pdfs:
        sys.exit("no PDF found")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    problems = 0
    for pdf in pdfs:
        reader = pypdf.PdfReader(str(pdf))
        box = reader.pages[0].mediabox
        size = f"{float(box.width) / 72 * 25.4:.0f}x{float(box.height) / 72 * 25.4:.0f} mm"
        fonts = fonts_of(reader)
        foreign = sorted(f for f in fonts if args.font.lower() not in f.lower())
        title = (reader.metadata or {}).get("/Title")
        document = pdfium.PdfDocument(str(pdf))
        images = []
        for i in range(len(document)):
            image = document[i].render(scale=args.scale).to_pil()
            suffix = "" if len(document) == 1 else f"-p{i + 1}"
            target = out / f"{pdf.stem}{suffix}.png"
            image.save(target)
            images.append(f"{target.name} ({image.size[0]}x{image.size[1]})")
        print(f"{pdf.name}: {len(reader.pages)} page(s), {size}, title {title!r}")
        print(f"  fonts: {', '.join(sorted(fonts)) or 'none'}")
        print(f"  png: {'; '.join(images)}")
        if foreign:
            problems += 1
            print(f"  PROBLEM: fonts without {args.font!r}: {foreign}; a glyph fell back")
        if args.pages and len(reader.pages) != args.pages:
            problems += 1
            print(f"  PROBLEM: {len(reader.pages)} pages, expected {args.pages}")
    print(f"{len(pdfs)} PDF(s) checked, PNGs in {out}, {problems} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
