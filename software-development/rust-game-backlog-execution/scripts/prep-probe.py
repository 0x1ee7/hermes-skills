"""A scratch asset root whose `level.probe` is `level.<level>` with the player's spawn moved to
tile (x, y): on the ground storey, or with --storey N inside storey N's `[level N at X Y]` block
(the spawn takes the block's storey). Prints the root. Run the game on it, for example with the
skill game-window-control:

    python prep-probe.py <level> <x> <y> [--storey N] [--root DIR] [--repo DIR]
    python <game-window-control>/scripts/gamewin.py launch --env ISO_ASSET_ROOT=<root> \
        --env ISO_AUDIO=0 --env ISO_EXIT_AFTER_FRAMES=60000 -- <repo>/target/debug/demo.exe probe
    python <game-window-control>/scripts/gamewin.py run --pid <pid> wait:2.5 shot:<png> tap:Tab ...

The root copies the repo's assets each run (new textures and maps come along); the game binary
is the repo's own, so rebuild it after code changes.
"""
import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path


def blocks_end(lines):
    """The grid's rows: from the first line that is neither empty nor a comment to the first
    section header."""
    grid = [i for i, line in enumerate(lines) if line and not line.startswith("//")]
    end = next(i for i in grid if lines[i].startswith("["))
    return grid[0], end


def main():
    args = argparse.ArgumentParser()
    args.add_argument("level")
    args.add_argument("x", type=int)
    args.add_argument("y", type=int)
    args.add_argument("--storey", type=int, default=0)
    args.add_argument("--repo", default=os.environ.get("ISO_REPO", "C:/Users/0x1de/dev/iso-engine"))
    args.add_argument("--root", default=str(Path(tempfile.gettempdir()) / "probe" / "assets"))
    a = args.parse_args()
    repo, root = Path(a.repo), Path(a.root)
    shutil.copytree(repo / "assets", root, dirs_exist_ok=True)
    lines = (repo / f"assets/maps/{a.level}.map").read_bytes().decode().split("\n")
    first, end = blocks_end(lines)
    # The old spawn becomes the ground beside it.
    for i in range(first, end):
        if "@" in lines[i]:
            j = lines[i].index("@")
            beside = lines[i][j - 1] if j > 0 else lines[i][j + 1]
            lines[i] = lines[i][:j] + beside + lines[i][j + 1:]
    if a.storey == 0:
        i, column = first + a.y, a.x
    else:
        header = re.compile(rf"^\[level {a.storey} at (\d+) (\d+)\]$")
        for h, line in enumerate(lines):
            m = header.match(line)
            if not m:
                continue
            x0, y0 = int(m.group(1)), int(m.group(2))
            rows = 0
            while h + 1 + rows < len(lines) and not lines[h + 1 + rows].startswith("["):
                rows += 1
            r, c = a.y - y0, a.x - x0
            if 0 <= r < rows and 0 <= c < len(lines[h + 1 + r]) and lines[h + 1 + r][c] != " ":
                i, column = h + 1 + r, c
                break
        else:
            raise SystemExit(f"no block of storey {a.storey} holds ({a.x}, {a.y})")
    row = lines[i]
    assert column < len(row) and row[column] not in " ^<>", \
        f"({a.x}, {a.y}) on storey {a.storey} is {row[column:column + 1]!r}, not a floor"
    lines[i] = row[:column] + "@" + row[column + 1:]
    (root / "maps/probe.map").write_bytes("\n".join(lines).encode())
    manifest = (repo / "assets/manifest.ron").read_bytes().decode()
    at = manifest.index(f'"level.{a.level}":')
    manifest = manifest[:at] + '"level.probe": "maps/probe.map",\n        ' + manifest[at:]
    (root / "manifest.ron").write_bytes(manifest.encode())
    print(root)


if __name__ == "__main__":
    main()
