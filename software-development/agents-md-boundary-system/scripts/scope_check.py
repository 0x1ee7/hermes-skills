#!/usr/bin/env python3
"""Stack-neutral boundary tooling: ownership table and scope check.

Reads the front matter (`boundary`, `owns`, `shares`) of every AGENTS.md under the repo, then:
  scope_check.py owners                  every tracked file and its owner; fails on none/ambiguous
  scope_check.py scope <b1,b2|*> [base]  fails when a file changed since `base` (default HEAD,
                                         plus untracked files) is outside the scope
Ownership: an `owns` entry ending in `/` owns everything below; the longest matching entry wins;
`shares` entries are editable without being owned. Stdlib only.
"""
import subprocess, sys, pathlib

EXEMPT = (".hermes/", ".claude/")  # agents' own scratch: never a leak, never needs an owner

def git(*a, root="."):
    return subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, check=True).stdout

def front_matter(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    block = text[4:text.index("\n---", 4)]
    out, key = {}, None
    for line in block.split("\n"):
        line = line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line[0] in " \t" and key:
            out[key] += [v.strip() for v in line.split(",") if v.strip()]
        else:
            key, _, val = line.partition(":")
            key = key.strip()
            out[key] = [v.strip() for v in val.split(",") if v.strip()]
    return out

def load(root):
    bounds = {}
    for f in git("ls-files", "*AGENTS.md", root=root).split():
        fm = front_matter(pathlib.Path(root, f))
        if fm and "boundary" in fm:
            bounds[fm["boundary"][0]] = fm
    assert bounds, "no boundaries found: an empty set would make every check pass"
    return bounds

def matches(entry, path):
    return path.startswith(entry) if entry.endswith("/") else path == entry

def owner(bounds, path):
    best, name, tie = -1, None, False
    for n, fm in bounds.items():
        for e in fm.get("owns", []):
            if matches(e, path):
                if len(e) > best: best, name, tie = len(e), n, False
                elif len(e) == best and n != name: tie = True
    return None if tie else name

def may_edit(bounds, b, path):
    fm = bounds[b]
    return owner(bounds, path) == b or any(matches(e, path) for e in fm.get("shares", []))

def main(argv):
    root = git("rev-parse", "--show-toplevel").strip()
    bounds = load(root)
    if argv[0] == "owners":
        bad = 0
        for f in git("ls-files", root=root).split("\n"):
            if f and not f.startswith(EXEMPT) and owner(bounds, f) is None:
                print(f"NO UNIQUE OWNER: {f}"); bad += 1
        print("ok" if not bad else f"{bad} file(s) without a unique owner"); return bool(bad)
    scope, base = argv[1], (argv[2] if len(argv) > 2 else "HEAD")
    if scope == "*": print("integrator scope: skipped"); return 0
    mine = scope.split(",")
    for m in mine: assert m in bounds, f"unknown boundary {m}; have {sorted(bounds)}"
    changed = set(git("diff", "--name-only", base, root=root).split()) | \
              set(git("ls-files", "--others", "--exclude-standard", root=root).split())
    leaks = [f"{f} (owned by {owner(bounds, f)})" for f in sorted(changed)
             if not f.startswith(EXEMPT) and not any(may_edit(bounds, m, f) for m in mine)]
    for l in leaks: print("LEAK:", l)
    print("ok" if not leaks else f"{len(leaks)} leak(s): revert or file an interface request")
    return bool(leaks)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("owners", "scope"): sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
