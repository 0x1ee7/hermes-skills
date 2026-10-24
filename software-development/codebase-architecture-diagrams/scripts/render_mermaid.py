#!/usr/bin/env python3
"""Render every ```mermaid block of a Markdown file with mermaid.js in headless Edge or Chrome:
one HTML page per diagram, OK or the parse error for each, and a PNG screenshot of each.

    python render_mermaid.py <markdown> <out dir> <mermaid.min.js> [width height]

The browser is $CHROME when set, else the usual Edge and Chrome install paths, else one on
PATH. Exits 1 when any diagram fails to parse. Standard library only.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

INSTALLS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
ON_PATH = ["google-chrome", "chromium", "chromium-browser", "microsoft-edge", "msedge", "chrome"]

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<style>body {{ font-family: sans-serif; margin: 16px; background: white; }}</style></head>
<body><div id="out">rendering</div>
<script src="{script}"></script>
<script>
mermaid.initialize({{ startOnLoad: false, securityLevel: "loose" }});
(async () => {{
  const out = document.getElementById("out");
  try {{
    const {{ svg }} = await mermaid.render("m{i}", {source});
    out.innerHTML = "<p>RESULT OK</p>" + svg;
  }} catch (e) {{
    out.textContent = "RESULT ERROR: " + (e && e.message ? e.message : e);
  }}
}})();
</script></body></html>"""


def browser():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for path in INSTALLS:
        if Path(path).exists():
            return path
    for name in ON_PATH:
        found = shutil.which(name)
        if found:
            return found
    sys.exit("no Edge or Chrome found; set CHROME=/path/to/browser")


def main():
    if len(sys.argv) not in (4, 6):
        sys.exit(__doc__)
    markdown, out = Path(sys.argv[1]), Path(sys.argv[2])
    script = Path(sys.argv[3]).resolve()
    width, height = (sys.argv[4], sys.argv[5]) if len(sys.argv) == 6 else ("1500", "1900")
    out.mkdir(parents=True, exist_ok=True)
    blocks = re.findall(r"```mermaid\n(.*?)```", markdown.read_text(encoding="utf-8"), re.S)
    print(f"{len(blocks)} mermaid blocks")
    common = [browser(), "--headless=new", "--disable-gpu", "--no-first-run",
              "--hide-scrollbars", "--virtual-time-budget=8000"]
    failed = 0
    for i, source in enumerate(blocks):
        page = (out / f"diagram_{i}.html").resolve()
        page.write_text(PAGE.format(script=script.as_uri(), i=i, source=json.dumps(source)),
                        encoding="utf-8")
        dom = subprocess.run(common + ["--dump-dom", page.as_uri()], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=120).stdout
        found = re.search(r"RESULT (OK|ERROR[^<]*)", dom)
        verdict = found.group(1).strip() if found else "NO RESULT (the page did not finish)"
        if not verdict.startswith("OK"):
            failed += 1
        shot = (out / f"diagram_{i}.png").resolve()
        subprocess.run(common + [f"--screenshot={shot}", f"--window-size={width},{height}",
                                 page.as_uri()], capture_output=True, timeout=120)
        first = source.strip().splitlines()[0] if source.strip() else "(empty)"
        print(f"diagram {i} ({first}): {verdict[:300]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
