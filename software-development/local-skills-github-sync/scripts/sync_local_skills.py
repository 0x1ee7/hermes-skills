#!/usr/bin/env python3
"""Sync local (user-created) Hermes skills into a git repo; commit + push when something changed.

  python sync_local_skills.py [--dry-run] [--prune] [--no-push] [--repo PATH] [--branch main]
                              [--remote origin] [--skills-dir PATH] [--classify auto|cli|fs]

Local = rows of `hermes skills list --source local` (fallback: the on-disk rule Hermes uses: not in
skills/.bundled_manifest and not in skills/.hub/lock.json). Builtin and hub skills are never copied.
Each local skill is mirrored to <repo>/<same relative path as in the skills dir>.

Exit codes: 0 ok/up-to-date/dry-run, 1 setup error, 2 repo state (dirty, wrong branch, diverged,
fetch failed), 3 blocked (secret-like string or file > 50 MB), 4 push failed.
The last line printed is always "RESULT: ...".
"""
import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = os.environ.get("HERMES_SKILLS_REPO", "D:/dev/hermes-skills")
IGNORE_DIRS = ("__pycache__", ".git", "node_modules", ".venv", ".pytest_cache", ".mypy_cache")
IGNORE_FILES = (".DS_Store", "Thumbs.db")
MAX_BYTES = 50 * 2**20
SCAN_BYTES = 5 * 2**20
SECRET_RES = [re.compile(p) for p in (
    r"gh[pousr]_[A-Za-z0-9]{36}", r"github_pat_[A-Za-z0-9_]{60,}",
    r"sk-ant-[A-Za-z0-9_-]{40,}", r"sk-proj-[A-Za-z0-9_-]{40,}", r"\bsk-[A-Za-z0-9]{48}\b",
    r"AKIA[0-9A-Z]{16}", r"xox[abprs]-\d{6,}-[A-Za-z0-9-]{10,}", r"AIza[0-9A-Za-z_-]{35}",
    r"\bhf_[A-Za-z0-9]{34}\b", r"-----BEGIN [A-Z ]*PRIVATE KEY-----\s*[\r\n]+[A-Za-z0-9+/=]{40,}",
)]


class Stop(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def log(msg=""):
    print(msg, flush=True)


def is_ignored_file(name):
    return name in IGNORE_FILES or name.endswith(".pyc")


def skill_name(skill_md):
    """Frontmatter `name:` (what Hermes lists), falling back to the directory name."""
    try:
        text = skill_md.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return skill_md.parent.name
    if text.startswith("---"):
        end = text.find("\n---", 3)
        front = text[3:end] if end > 0 else text[3:]
        m = re.search(r"^name:\s*['\"]?([^'\"\r\n]+?)['\"]?\s*$", front, re.M)
        if m:
            return m.group(1).strip()
    return skill_md.parent.name


def scan_skills(root):
    """{relative dir: skill name} for every skill under root (dot dirs skipped, nested SKILL.md ignored)."""
    found = {}
    for cur, dirs, files in os.walk(root):
        here = Path(cur)
        if "SKILL.md" in files and here != Path(root):
            found[here.relative_to(root).as_posix()] = skill_name(here / "SKILL.md")
            dirs[:] = []
            continue
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in IGNORE_DIRS)
    return found


def files_of(d):
    out = {}
    for cur, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in IGNORE_DIRS]
        for f in files:
            if not is_ignored_file(f):
                p = Path(cur) / f
                out[p.relative_to(d).as_posix()] = p
    return out


def differs(src, dst):
    a, b = files_of(src), files_of(dst)
    return a.keys() != b.keys() or any(not filecmp.cmp(a[k], b[k], shallow=False) for k in a)


def cli_local_names():
    """Names from `hermes skills list --source local`, or (None, reason) if unavailable/unparseable."""
    exe = shutil.which("hermes")
    if not exe:
        return None, "hermes CLI not on PATH"
    env = dict(os.environ, COLUMNS="400", PYTHONIOENCODING="utf-8", PYTHONUTF8="1", NO_COLOR="1", TERM="dumb")
    try:
        p = subprocess.run([exe, "skills", "list", "--source", "local"], capture_output=True, env=env, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"hermes CLI failed ({e})"
    out = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", p.stdout.decode("utf-8", "replace"))
    if p.returncode != 0:
        return None, f"`hermes skills list` exited with {p.returncode}"
    rows = []
    for line in out.splitlines():
        cells = [c.strip() for c in re.split(r"[\u2502\u2503|]", line)]
        if len(cells) >= 6 and cells[1] and cells[1] != "Name":
            rows.append((cells[1], cells[3]))
    m = re.search(r"(\d+) local\b", out)
    if not m or int(m.group(1)) != len(rows):
        return None, "could not parse `hermes skills list` output"
    if any(n.endswith(("\u2026", "...")) for n, _ in rows):
        return None, "`hermes skills list` truncated skill names"
    return [n for n, src in rows if src in ("local", "create_dir")], None


def fs_local_names(skills_dir, catalog):
    """Hermes' own rule: not in the bundled manifest and not hub-installed."""
    skip = set()
    manifest = skills_dir / ".bundled_manifest"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                skip.add(line.partition(":")[0].strip())
    lock = skills_dir / ".hub" / "lock.json"
    if lock.is_file():
        try:
            skip |= set(json.loads(lock.read_text(encoding="utf-8-sig")).get("installed") or {})
        except (ValueError, AttributeError) as e:
            raise Stop(1, f"cannot parse {lock}: {e}")
    return [name for rel, name in catalog.items() if name not in skip and rel.rsplit("/", 1)[-1] not in skip]


def resolve(names, catalog):
    """Map skill names to relative dirs inside the skills dir."""
    by_name, by_dir = {}, {}
    for rel, name in catalog.items():
        by_name.setdefault(name, []).append(rel)
        by_dir.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
    rels, missing = set(), []
    for n in names:
        hits = [n] if n in catalog else (by_name.get(n) or by_dir.get(n) or [])
        if len(hits) > 1:
            raise Stop(1, f"skill name {n!r} matches several dirs: {hits}")
        if hits:
            rels.add(hits[0])
        else:
            missing.append(n)
    return sorted(rels), missing


def publish_problems(skills_dir, rels):
    problems = []
    for rel in rels:
        for frel, p in files_of(skills_dir / rel).items():
            size = p.stat().st_size
            if size > MAX_BYTES:
                problems.append(f"{rel}/{frel}: {size / 2**20:.0f} MB file (over 50 MB)")
                continue
            if size > SCAN_BYTES:
                continue
            text = p.read_bytes().decode("utf-8", "ignore")
            for rx in SECRET_RES:
                for m in rx.finditer(text):
                    tok = m.group(0)
                    if len(set(tok[-16:])) <= 4:  # xxxx / 0000 style placeholders
                        continue
                    line = text.count("\n", 0, m.start()) + 1
                    problems.append(f"{rel}/{frel}:{line}: secret-like string {tok[:8]}...")
    return problems


class Repo:
    def __init__(self, path):
        self.path = path
        self.safe = path.as_posix()

    def run(self, *args):
        return subprocess.run(["git", "-c", f"safe.directory={self.safe}", "-C", str(self.path), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def out(self, *args, code=2):
        p = self.run(*args)
        if p.returncode != 0:
            raise Stop(code, f"git {' '.join(args)} failed: {(p.stderr or p.stdout).strip()}")
        return p.stdout.strip()


def rmtree(path):
    def retry(func, p, _):
        os.chmod(p, 0o700)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def commit_message(added, updated, removed):
    def short(rels):
        return ", ".join(r.rsplit("/", 1)[-1] for r in rels)
    parts = [f"{verb} {short(rels)}" for verb, rels in (("add", added), ("update", updated), ("remove", removed)) if rels]
    kind = "feat" if added else "chore"
    subject = f"{kind}(skills): {'; '.join(parts)}"
    if len(subject) > 72:
        subject = f"{kind}(skills): sync local skills (+{len(added)} ~{len(updated)} -{len(removed)})"
    body = "\n".join([f"added:   {r}" for r in added] + [f"updated: {r}" for r in updated]
                     + [f"removed: {r}" for r in removed])
    return subject, body


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Sync local Hermes skills to a git repo and push.")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--skills-dir")
    ap.add_argument("--classify", choices=("auto", "cli", "fs"), default="auto")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true", help="delete repo skills that are no longer local")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    hermes_home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
    skills_dir = Path(a.skills_dir) if a.skills_dir else hermes_home / "skills"
    repo = Repo(Path(a.repo).resolve())
    if not skills_dir.is_dir():
        raise Stop(1, f"skills dir not found: {skills_dir}")
    if not (repo.path / ".git").exists():
        raise Stop(1, f"not a git repo: {repo.path}")

    # 1. repo state
    branch = repo.out("rev-parse", "--abbrev-ref", "HEAD")
    if branch != a.branch:
        raise Stop(2, f"repo is on branch {branch!r}, expected {a.branch!r}")
    dirty = repo.out("status", "--porcelain")
    if dirty:
        raise Stop(2, f"repo has uncommitted changes (commit or discard them first):\n{dirty}")
    ahead = behind = 0
    fetch = repo.run("fetch", "--quiet", a.remote, a.branch)
    if fetch.returncode == 0:
        counts = repo.out("rev-list", "--left-right", "--count", f"HEAD...{a.remote}/{a.branch}")
        ahead, behind = map(int, counts.split())
    elif "couldn't find remote ref" in fetch.stderr:
        ahead = int(repo.out("rev-list", "--count", "HEAD"))  # first push of this branch
    elif a.dry_run or a.no_push:
        log(f"warning: fetch failed, continuing without remote state: {fetch.stderr.strip()}")
    else:
        raise Stop(2, f"git fetch failed: {fetch.stderr.strip()}")
    if ahead and behind:
        raise Stop(2, f"{a.branch} diverged from {a.remote}/{a.branch} (ahead {ahead}, behind {behind}); "
                      "resolve manually, never force-push")
    if behind and not a.dry_run:
        repo.out("merge", "--ff-only", "--quiet", f"{a.remote}/{a.branch}")
        log(f"fast-forwarded {behind} commit(s) from {a.remote}/{a.branch}")
        behind = 0

    # 2. which skills are local
    catalog = scan_skills(skills_dir)
    names, why = (None, None) if a.classify == "fs" else cli_local_names()
    fs_names = fs_local_names(skills_dir, catalog)
    if names is None:
        if a.classify == "cli":
            raise Stop(1, why)
        if why:
            log(f"warning: {why}; using the on-disk rule (not bundled, not hub-installed)")
        names, how = fs_names, "on-disk rule"
    else:
        how = "hermes skills list --source local"
        disagree = set(names) ^ set(fs_names)
        if disagree:
            log(f"warning: CLI and on-disk rule disagree on: {', '.join(sorted(disagree))} (using CLI)")
    local, missing = resolve(names, catalog)
    for n in missing:
        log(f"warning: local skill {n!r} is not under {skills_dir} (create_dir/external?), skipped")
    log(f"local skills via {how}: {len(local)}")

    # 3. plan
    in_repo = scan_skills(repo.path)
    new = [r for r in local if r not in in_repo]
    upd = [r for r in local if r in in_repo and differs(skills_dir / r, repo.path / r)]
    stale = sorted(set(in_repo) - set(local))
    removed = stale if a.prune else []
    for label, rels in (("new", new), ("updated", upd), ("removed" if a.prune else "stale", stale)):
        for r in rels:
            log(f"  {label:<8} {r}")
    if stale and not a.prune:
        log("  (stale = in repo but no longer local; kept, --prune deletes them)")
    if a.dry_run:
        extra = f", fast-forward {behind}" if behind else ""
        log(f"RESULT: dry-run: would add {len(new)}, update {len(upd)}, remove {len(removed)}{extra}"
            f", push {'no' if a.no_push else 'yes'}")
        return 0
    if not (new or upd or removed or ahead):
        log("RESULT: up-to-date")
        return 0

    # 4. never publish secrets or huge files
    problems = publish_problems(skills_dir, new + upd)
    if problems:
        raise Stop(3, "refusing to copy; fix these first:\n" + "\n".join(f"  {p}" for p in problems))

    # 5. mirror, commit, push
    ignore = shutil.ignore_patterns(*IGNORE_DIRS, *IGNORE_FILES, "*.pyc")
    for r in new + upd:
        dst = repo.path / r
        if dst.exists():
            rmtree(dst)
        shutil.copytree(skills_dir / r, dst, ignore=ignore)
    for r in removed:
        rmtree(repo.path / r)
        parent = (repo.path / r).parent
        while repo.path in parent.parents and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    repo.out("add", "-A")
    if repo.out("status", "--porcelain"):
        subject, body = commit_message(new, upd, removed)
        repo.out("commit", "-q", "-m", subject, "-m", body)
        log(f"committed: {subject}")
    elif not ahead:
        log("RESULT: up-to-date")
        return 0
    head = repo.out("rev-parse", "HEAD")
    if a.no_push:
        log(f"RESULT: committed {head[:7]} (not pushed)")
        return 0
    push = repo.run("push", "--quiet", a.remote, a.branch)
    if push.returncode != 0:
        raise Stop(4, f"git push failed: {(push.stderr or push.stdout).strip()}")
    remote = repo.out("ls-remote", a.remote, f"refs/heads/{a.branch}", code=4).split()
    if not remote or remote[0] != head:
        raise Stop(4, f"push not visible on {a.remote}: remote {remote[:1]} != local {head[:7]}")
    log(f"RESULT: pushed {head[:7]} to {a.remote}/{a.branch} (+{len(new)} ~{len(upd)} -{len(removed)})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as e:
        print(str(e), flush=True)
        print(f"RESULT: blocked: {str(e).splitlines()[0]}", flush=True)
        sys.exit(e.code)
