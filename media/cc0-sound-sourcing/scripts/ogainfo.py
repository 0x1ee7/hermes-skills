"""Facts from saved OpenGameArt pages: title, author ("Submitted by"), licence, body text and
the direct file links. Save a page first:

    curl -sL -A 'Mozilla/5.0' -o page.html https://opengameart.org/content/<slug>
    python3 ogainfo.py page.html [more.html ...]
"""
import html
import re
import sys


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


for path in sys.argv[1:]:
    text = open(path, encoding="utf-8", errors="replace").read()
    title = re.search(r"<title>([^<]+)</title>", text)
    author = (re.search(r"field-name-author-submitter.*?<a[^>]*>([^<]+)</a>", text, re.S)
              or re.search(r"Submitted by.*?<a[^>]*>([^<]+)</a>", text, re.S))
    licences = re.search(r"field-name-field-art-licenses.*?</div>\s*</div>", text, re.S)
    lic = re.findall(r">(CC0|CC-BY[^<]*|GPL[^<]*|OGA-BY[^<]*)<", licences.group(0)) if licences else []
    body = re.search(r'field-name-body.*?<div class="field-item[^>]*>(.*?)</div>\s*</div>', text, re.S)
    files = sorted(set(re.findall(
        r'href="(https://opengameart.org/sites/default/files/[^"]+\.(?:wav|ogg|zip|7z|mp3|flac))"',
        text)))
    print("==", path)
    print("title:", strip(title.group(1)) if title else "?")
    print("author:", strip(author.group(1)) if author else "?")
    print("licence:", ", ".join(sorted(set(lic))) or "?")
    print("body:", strip(body.group(1))[:700] if body else "?")
    for f in files:
        print("file:", f)
