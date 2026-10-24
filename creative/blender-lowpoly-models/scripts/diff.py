"""Pixel difference of two captures: python diff.py a.png b.png

Two captures of one build of a static scene should give 0 %; use that as the noise floor before
reading anything into a difference.
"""
import sys

from PIL import Image, ImageChops

a = Image.open(sys.argv[1]).convert("RGB")
b = Image.open(sys.argv[2]).convert("RGB")
d = ImageChops.difference(a, b).convert("L")
h = d.histogram()
n = sum(h)
print(f"differing {100 * sum(h[1:]) / n:.3f} %, by >2 levels {100 * sum(h[3:]) / n:.3f} %, "
      f"by >16 levels {100 * sum(h[17:]) / n:.3f} %, max {d.getextrema()[1]}")
