"""Print every `file:line` reference of a Markdown file next to the line it points at, so each
can be checked by eye after the code moved. A bare `:NN` right after a reference reuses that
file. Files are found by their path from the repo root, or else by name anywhere in the repo.

    python check_refs.py <doc.md> [repo root]

Read every printed line: it must be the declaration, constant or call the text names. Exits 1
when a file is missing or ambiguous, or a line lies past its end.
"""
import re
import sys
from pathlib import Path

SKIP = {".git", "target", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}


def files_by_name(root):
    names = {}
    for path in root.rglob("*"):
        if path.is_file() and not SKIP.intersection(path.relative_to(root).parts):
            names.setdefault(path.name, []).append(path)
    return names


def resolve(name, root, names):
    direct = root / name
    if direct.is_file():
        return direct, None
    found = [p for p in names.get(Path(name).name, []) if p.as_posix().endswith(name)]
    if len(found) == 1:
        return found[0], None
    return None, "missing file" if not found else f"{len(found)} files match"


def main():
    doc = Path(sys.argv[1])
    root = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.cwd()
    names = files_by_name(root)
    pattern = re.compile(r"`([\w./-]+\.[A-Za-z0-9]+):(\d+)`|`:(\d+)`")
    last, problems = None, 0
    for match in pattern.finditer(doc.read_text(encoding="utf-8")):
        if match.group(1):
            name, line = match.group(1), int(match.group(2))
            last = name
        elif last:
            name, line = last, int(match.group(3))
        else:
            continue
        path, error = resolve(name, root, names)
        if error:
            print(f"{name}:{line}  {error.upper()}")
            problems += 1
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if line > len(lines):
            print(f"{name}:{line}  PAST THE END ({len(lines)} lines)")
            problems += 1
            continue
        print(f"{name}:{line}  {lines[line - 1].strip()[:100]}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
