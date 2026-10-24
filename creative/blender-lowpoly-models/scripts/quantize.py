"""Shrink a screenshot for docs: python quantize.py in.png out.png

A 256-colour palette (octree, no dithering) keeps flat-shaded low-poly scenes sharp at a fifth of
the size. Median cut looked similar overall but greyed out small saturated regions (a
character's shirt); compare a crop of the important detail before committing.
"""
import os
import sys

from PIL import Image

src, dst = sys.argv[1], sys.argv[2]
image = Image.open(src).convert("RGB")
image.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(
    dst, optimize=True)
print(f"{dst}: {os.path.getsize(dst)} bytes (was {os.path.getsize(src)})")
