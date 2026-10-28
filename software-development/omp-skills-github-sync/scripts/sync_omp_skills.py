#!/usr/bin/env python3
"""Compare the skills omp loads with a git repo of skills; commit and push what changed.

  python sync_omp_skills.py [--dry-run] [--no-push] [--repo PATH] [--branch main] [--remote origin]

omp skills = `omp skill list --json`. Skills whose folder is inside the repo (skills.customDirectories)
are used in place. User-level skills kept outside it (native:user ~/.omp/agent/skills, omp-managed:user
autolearn skills, custom:user dirs elsewhere) are copied to <repo>/omp/<folder>, which is rebuilt from
them on every run. Project, registry, plugin and other tools' skills are not copied.
The working tree is compared with HEAD per skill folder (<category>/<skill>), committed and pushed.

Exit codes: 0 ok/up-to-date/dry-run, 1 setup error, 2 repo state (wrong branch, diverged, fetch or
fast-forward failed), 3 blocked (secret-like string or file > 50 MB), 4 push failed.
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

DEFAULT_REPO = os.environ.get("OMP_SKILLS_REPO", "D:/dev/hermes-skills")
MIRROR = "omp"
MIRRORED_SOURCES = ("native:user", "omp-managed:user", "custom:user")
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


class Repo:
    def __init__(self, path):
        self.path = path
        self.safe = path.as_posix()

    def run(self, *args):
        return subprocess.run(["git", "-c", f"safe.directory={self.safe}", "-C", str(self.path), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def out(self, *args, code=2, strip=True):
        p = self.run(*args)
        if p.returncode != 0:
            raise Stop(code, f"git {' '.join(args)} failed: {(p.stderr or p.stdout).strip()}")
        return p.stdout.strip() if strip else p.stdout


def omp_skills(cwd):
    """Skills omp loads, from `omp skill list --json`; omp's warnings are printed."""
    exe = shutil.which("omp")
    if not exe:
        raise Stop(1, "omp CLI not on PATH")
    try:
        p = subprocess.run([exe, "skill", "list", "--json"], cwd=str(cwd), stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=300)
        if p.returncode != 0:
            raise Stop(1, f"`omp skill list --json` exited with {p.returncode}: "
                          f"{p.stderr.decode('utf-8', 'replace').strip()}")
        data = json.loads(p.stdout.decode("utf-8", "replace"))
        skills = list(data["skills"])
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as e:
        raise Stop(1, f"`omp skill list --json` failed: {e}")
    for w in data.get("warnings") or []:
        log(f"omp warning: {w.get('message', w) if isinstance(w, dict) else w}")
    return skills


def inside(path, root):
    try:
        rel = os.path.relpath(os.path.realpath(path), os.path.realpath(root))
    except ValueError:  # another drive
        return False
    return rel not in (os.curdir, os.pardir) and not rel.startswith(os.pardir + os.sep)


def files_of(d):
    out = {}
    for cur, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if x not in IGNORE_DIRS]
        for f in files:
            if f not in IGNORE_FILES and not f.endswith(".pyc"):
                p = Path(cur) / f
                out[p.relative_to(d).as_posix()] = p
    return out


def differs(src, dst):
    a, b = files_of(src), files_of(dst)
    return a.keys() != b.keys() or any(not filecmp.cmp(a[k], b[k], shallow=False) for k in a)


def rmtree(path):
    def retry(func, p, _):
        os.chmod(p, 0o700)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def sync_mirror(repo, sources, apply):
    """Make <repo>/omp hold one copy per source skill; returns [(label, folder)] that differ."""
    root = repo / MIRROR
    plan = []
    for d in (sorted(root.iterdir()) if root.is_dir() else []):
        if d.is_dir() and d.name not in sources:
            plan.append(("removed", f"{MIRROR}/{d.name}"))
            if apply:
                rmtree(d)
    for name, src in sorted(sources.items()):
        dst = root / name
        if dst.exists() and not differs(src, dst):
            continue
        plan.append(("updated" if dst.exists() else "new", f"{MIRROR}/{name}"))
        if apply:
            if dst.exists():
                rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*IGNORE_DIRS, *IGNORE_FILES, "*.pyc"))
    if apply and root.is_dir() and not any(root.iterdir()):
        root.rmdir()
    return plan


def compare(repo):
    """Working tree vs HEAD per skill folder: ({"new"|"updated"|"removed": [folder]}, [changed paths])."""
    raw = repo.out("status", "--porcelain=v1", "-z", "-uall", strip=False).split("\0")
    groups, paths, i = {}, [], 0
    while i < len(raw):
        entry = raw[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if xy[0] in "RC":
            i += 1  # skip the rename/copy source; the new path carries the change
        parts = path.split("/")
        key = "/".join(parts[:2]) if len(parts) > 2 else path
        groups.setdefault(key, {})[path] = xy
        paths.append(path)
    plan = {"new": [], "updated": [], "removed": []}
    for key, codes in sorted(groups.items()):
        xy = codes.get(f"{key}/SKILL.md") or codes.get(key) or ""
        plan["new" if xy == "??" or "A" in xy else "removed" if "D" in xy else "updated"].append(key)
    return plan, paths


def publish_problems(repo, paths):
    problems = []
    for rel in paths:
        p = repo / rel
        if not p.is_file():
            continue
        size = p.stat().st_size
        if size > MAX_BYTES:
            problems.append(f"{rel}: {size / 2**20:.0f} MB file (over 50 MB)")
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
                problems.append(f"{rel}:{line}: secret-like string {tok[:8]}...")
    return problems


def commit_message(added, updated, removed):
    def short(rels):
        return ", ".join(r.rsplit("/", 1)[-1] for r in rels)
    parts = [f"{verb} {short(rels)}" for verb, rels in (("add", added), ("update", updated), ("remove", removed)) if rels]
    kind = "feat" if added else "chore"
    subject = f"{kind}(skills): {'; '.join(parts)}"
    if len(subject) > 72:
        subject = f"{kind}(skills): sync omp skills (+{len(added)} ~{len(updated)} -{len(removed)})"
    body = "\n".join([f"added:   {r}" for r in added] + [f"updated: {r}" for r in updated]
                     + [f"removed: {r}" for r in removed])
    return subject, body


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description="Compare omp skills with a git repo, commit and push what changed.")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--dry-run", action="store_true", help="compare only; change nothing")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    repo = Repo(Path(a.repo).resolve())
    if not (repo.path / ".git").exists():
        raise Stop(1, f"not a git repo: {repo.path}")

    # 1. branch and remote state
    branch = repo.out("rev-parse", "--abbrev-ref", "HEAD")
    if branch != a.branch:
        raise Stop(2, f"repo is on branch {branch!r}, expected {a.branch!r}")
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

    # 2. omp skills: inside the repo they are used in place; user-level ones elsewhere are copied in
    mirror_root = repo.path / MIRROR
    sources, in_repo, skipped = {}, 0, []
    for s in omp_skills(repo.path):
        base = Path(s.get("baseDir") or os.path.dirname(s["filePath"]))
        if inside(base, repo.path):
            if inside(base, mirror_root):
                raise Stop(1, f"omp loads {base} from {mirror_root}, which this script rebuilds; "
                              "remove that folder from skills.customDirectories")
            in_repo += 1
        elif s.get("source") in MIRRORED_SOURCES:
            if base.name in sources:
                raise Stop(1, f"two omp skills share the folder name {base.name!r}: {sources[base.name]} and {base}")
            sources[base.name] = base
        else:
            skipped.append(f"{s.get('name')} ({s.get('source')})")
    log(f"omp skills: {in_repo} in the repo, {len(sources)} outside it (copied to {MIRROR}/)"
        + (f"; skipped: {', '.join(skipped)}" if skipped else ""))

    # 3. compare with HEAD
    mirror_plan = sync_mirror(repo.path, sources, apply=not a.dry_run)
    plan, paths = compare(repo)
    if a.dry_run:  # the copies were not refreshed; show what refreshing them would change
        for label, folder in mirror_plan:
            if folder not in plan[label]:
                plan[label].append(folder)
    added, updated, removed = plan["new"], plan["updated"], plan["removed"]
    for label, folders in (("new", added), ("updated", updated), ("removed", removed)):
        for folder in folders:
            log(f"  {label:<8} {folder}")
    if ahead:
        log(f"  {ahead} local commit(s) not on {a.remote}/{a.branch} yet")
    if a.dry_run:
        extra = f", fast-forward {behind}" if behind else ""
        will_push = bool(added or updated or removed or paths or ahead) and not a.no_push
        log(f"RESULT: dry-run: would add {len(added)}, update {len(updated)}, remove {len(removed)}{extra}"
            f", push {'yes' if will_push else 'no'}")
        return 0
    if not (paths or ahead):
        log("RESULT: up-to-date")
        return 0

    # 4. never publish secrets or huge files
    problems = publish_problems(repo.path, paths)
    if problems:
        raise Stop(3, "refusing to commit; fix these first:\n" + "\n".join(f"  {p}" for p in problems))

    # 5. commit, push, verify
    if paths:
        repo.out("add", "-A")
        subject, body = commit_message(added, updated, removed)
        repo.out("commit", "-q", "-m", subject, "-m", body)
        log(f"committed: {subject}")
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
    log(f"RESULT: pushed {head[:7]} to {a.remote}/{a.branch} (+{len(added)} ~{len(updated)} -{len(removed)})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Stop as e:
        print(str(e), flush=True)
        print(f"RESULT: blocked: {str(e).splitlines()[0]}", flush=True)
        sys.exit(e.code)
