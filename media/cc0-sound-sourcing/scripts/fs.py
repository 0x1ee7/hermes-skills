"""Freesound without an API key: search pages and sound pages are public HTML, and the HQ
preview (OGG Vorbis, about 192 kb/s) is on the public CDN.

    python3 fs.py search footstep gravel          # CC0-filtered results, one per line
    python3 fs.py by Nox_Sound footsteps          # the same, within one user's sounds
    python3 fs.py info 384880                     # the sound page's facts as JSON
    python3 fs.py get 384880 [384890 ...]         # verify CC0, fetch the HQ preview

Downloads go to dl/fs/<id>.ogg and dl/fs/<id>.json (title, author, licence, url, description)
next to this script. Pause a few seconds between calls; the site rate-limits bursts.
Standard library plus curl.
"""
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def fetch(url, out=None):
    args = ["curl", "-sL", "--max-time", "90", "-A", UA, url]
    if out:
        subprocess.run(args + ["-o", str(out)], check=True)
        return None
    return subprocess.run(args, check=True, capture_output=True).stdout.decode("utf-8", "replace")


def players(text):
    """The data-* attributes of every player widget on a page (one per sound)."""
    for m in re.finditer(r'class="bw-player[^"]*"(.*?)>', text, re.S):
        attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', m.group(1)))
        if "sound-id" in attrs:
            yield attrs


def search(query, pages=2, username=None):
    seen = set()
    for page in range(1, pages + 1):
        q = urllib.parse.quote_plus(query)
        who = f"+username:%22{urllib.parse.quote_plus(username)}%22" if username else ""
        url = (f"https://freesound.org/search/?q={q}&f=license:%22Creative+Commons+0%22{who}"
               f"&page={page}")
        for a in players(fetch(url)):
            if a["sound-id"] in seen:
                continue
            seen.add(a["sound-id"])
            print(f"{a['sound-id']:>7} {float(a['duration']):6.2f}s  {a['username']:<22} {a['title']}")


def info(sound_id):
    page = fetch(f"https://freesound.org/s/{sound_id}/")
    title = re.search(r"<title>([^<]+)</title>", page)
    url = re.search(r'<link rel="canonical" href="([^"]+)"', page)
    licence = re.search(r'href="(https?://creativecommons.org/[^"]+)"', page)
    author = re.search(r'/people/([^/"]+)/sounds/%s/' % sound_id, page)
    desc = re.search(r'id="soundDescriptionSection"(.*?)</div>', page, re.S)
    ogg = re.search(r'data-ogg="([^"]+)"', page)
    pack = re.search(r'href="(/people/[^/"]+/packs/\d+/)"', page)
    clean = title.group(1).replace("Freesound - ", "") if title else "?"
    return dict(
        id=sound_id,
        title=clean.split(" by ")[0].strip(),
        author=author.group(1) if author else "?",
        licence=licence.group(1) if licence else "?",
        url=url.group(1) if url else f"https://freesound.org/s/{sound_id}/",
        pack=f"https://freesound.org{pack.group(1)}" if pack else None,
        description=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", desc.group(1))).strip()[:500]
        if desc else "",
        preview=ogg.group(1).replace("-lq.", "-hq.") if ogg else None,
    )


def get(sound_id):
    facts = info(sound_id)
    out = HERE / "dl" / "fs"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{sound_id}.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
    if "publicdomain/zero" not in facts["licence"]:
        print(f"{sound_id}: not CC0 ({facts['licence']}), skipped")
        return
    if not facts["preview"]:
        print(f"{sound_id}: no preview found")
        return
    fetch(facts["preview"], out / f"{sound_id}.ogg")
    print(f"{sound_id}: {facts['title']} by {facts['author']} (CC0) -> "
          f"{(out / f'{sound_id}.ogg').stat().st_size} bytes")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "search":
        search(" ".join(args))
    elif cmd == "by":
        search(" ".join(args[1:]), pages=4, username=args[0])
    elif cmd == "info":
        print(json.dumps(info(args[0]), indent=1))
    elif cmd == "get":
        for sound_id in args:
            get(sound_id)
