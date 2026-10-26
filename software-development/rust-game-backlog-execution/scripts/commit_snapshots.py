"""Turn gated snapshots (snap.sh) into a chain of commits on top of HEAD, in order.

Run from the repository root:

    python commit_snapshots.py --snaps <dir> [--tokens docs/x-queue.md]
        [--asset-list docs/asset-list.md --asset-cmd "python3 tools/list_assets.py"
         --asset-from <label>] [--dry-run]

<dir> holds snapshots.txt (`<label> <tree>` lines, in order) and msgs/<label>.txt. Each commit
takes its snapshot's tree as gated, with two things only the commits can give: `@@<label>@@`
tokens in the --tokens file become the short hashes of those labels' commits (a token naming a
label not yet committed stops the run), and from the --asset-from label on, the --asset-list
file is the one --asset-cmd writes in a worktree at that commit's parent (for a list that
cites the commits that added each asset). --dry-run leaves the chain at
refs/heads/snapshots-dryrun and moves nothing. Otherwise the current branch moves to the tip,
the index is reset to it and the working tree gets the filled-in files, so `git status` lists
only work done after the last snapshot.
"""
import argparse
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

DRY_REF = "refs/heads/snapshots-dryrun"


def git(*args, inp=None, env=None, cwd=None, check=True):
    result = subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True, env=env)
    if check and result.returncode != 0:
        sys.exit(f"git {' '.join(args)}: {result.stderr.decode()}")
    return result


def out(*args, **kwargs):
    return git(*args, **kwargs).stdout.decode().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snaps", required=True, type=Path)
    parser.add_argument("--tokens")
    parser.add_argument("--asset-list")
    parser.add_argument("--asset-cmd")
    parser.add_argument("--asset-from")
    parser.add_argument("--dry-run", action="store_true")
    a = parser.parse_args()
    if bool(a.asset_list) != bool(a.asset_cmd) or bool(a.asset_list) != bool(a.asset_from):
        sys.exit("--asset-list, --asset-cmd and --asset-from go together")
    snaps = [line.split() for line in (a.snaps / "snapshots.txt").read_text().splitlines()
             if line.strip()]
    labels = [label for label, _ in snaps]
    if a.asset_from and a.asset_from not in labels:
        sys.exit(f"--asset-from {a.asset_from}: no such snapshot")
    for label in labels:
        if not (a.snaps / "msgs" / f"{label}.txt").is_file():
            sys.exit(f"{label}: no message msgs/{label}.txt")
    branch = out("symbolic-ref", "HEAD")
    head = out("rev-parse", "HEAD")
    env = dict(os.environ, GIT_INDEX_FILE=str(a.snaps / "commit.index"))
    hashes = {}
    asset_blob = None
    parent = head
    for label, tree in snaps:
        git("read-tree", tree, env=env)
        if a.tokens and git("cat-file", "-e", f"{tree}:{a.tokens}", check=False).returncode == 0:
            text = git("show", f"{tree}:{a.tokens}").stdout.decode()
            for done, sha in hashes.items():
                text = text.replace(f"@@{done}@@", sha[:7])
            left = re.findall(r"@@[\w.-]+@@", text)
            if left:
                sys.exit(f"{label}: tokens for commits not made yet: {left}")
            blob = out("hash-object", "-w", "--stdin", inp=text.encode())
            git("update-index", "--cacheinfo", f"100644,{blob},{a.tokens}", env=env)
        if label == a.asset_from:
            asset_blob = asset_list(a, parent)
        if asset_blob:
            git("update-index", "--cacheinfo", f"100644,{asset_blob},{a.asset_list}", env=env)
        final_tree = out("write-tree", env=env)
        message = (a.snaps / "msgs" / f"{label}.txt").read_bytes()
        sha = out("commit-tree", final_tree, "-p", parent, inp=message)
        hashes[label] = parent = sha
        print(f"{sha[:7]} {label}: {message.decode().splitlines()[0]}")
    if a.dry_run:
        git("update-ref", DRY_REF, parent)
        print(f"dry run: {DRY_REF} at {parent[:7]}; {branch} still at {head[:7]}")
        return
    git("update-ref", branch, parent, head)
    git("reset", "-q")
    for path in filter(None, (a.tokens, a.asset_list)):
        if git("cat-file", "-e", f"{parent}:{path}", check=False).returncode == 0:
            Path(path).write_bytes(git("show", f"{parent}:{path}").stdout)
    print(f"{branch} at {parent[:7]}")
    print(out("status", "--short") or "clean")


def asset_list(a, commit):
    """The asset list as --asset-cmd writes it with `commit` checked out."""
    where = a.snaps / "wt_assets"
    if where.exists():
        git("worktree", "remove", "--force", str(where))
    git("worktree", "add", "--detach", str(where), commit)
    try:
        subprocess.run(shlex.split(a.asset_cmd), cwd=where, check=True, capture_output=True)
        return out("hash-object", "-w", a.asset_list, cwd=str(where))
    finally:
        git("worktree", "remove", "--force", str(where))
        git("worktree", "prune")


if __name__ == "__main__":
    main()
