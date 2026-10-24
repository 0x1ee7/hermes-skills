"""Check agent files against a Cargo workspace: drafts before they are written, or the files
in place afterwards.

Usage: python3 validate_agent_drafts.py <repo root> [<drafts dir> | --in-place]
       (the drafts dir defaults to <repo root>/.hermes/agents-drafts)

Drafts mirror the repo: `<dir>/AGENTS.draft.md` stands for `<dir>/AGENTS.md`, and
`CLAUDE.shim.draft.md` at the drafts root stands for the `CLAUDE.md` beside every agent file,
the root one included (the root CLAUDE.md's text moves into the root AGENTS.md). With
`--in-place` the script reads the AGENTS.md and CLAUDE.md files already in the repo.

The referee suite's checks:
- front matter keys (`#` starts a comment);
- [dependencies] and [dev-dependencies] against `depends`, `external` and `dev-depends`;
- `forbidden`, and `never-in-tree` (via `cargo tree`);
- one owner per file, and every entry matches a file;
- sections in order, and a CLAUDE.md beside every agent file that imports @AGENTS.md;
- contract items public in non-test code; content keys in MANIFEST.
Checks the referee does not make:
- every manifest key that Rust code names (tests included) is in the content contract;
- relative links resolve; no line passes LINE_LIMIT (tables and long code spans excepted);
- the root file plus any boundary file fits HERMES_BUDGET, what Hermes loads in full;
- drafts only: every line of a root CLAUDE.md that is not a shim yet reappears in the root
  AGENTS.md draft (printed as notes: rewording on purpose is fine).
The script never changes the repo. It assumes an explicit `members = [...]` list and one
dependency per line. Adapt the constants below to the project. Before trusting it,
mutation-check it: break one draft, see the problem reported, restore the draft.
"""
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
IN_PLACE = sys.argv[2:3] == ["--in-place"]
if IN_PLACE:
    DRAFTS = ROOT
elif len(sys.argv) > 2:
    DRAFTS = Path(sys.argv[2]).resolve()
else:
    DRAFTS = ROOT / ".hermes" / "agents-drafts"
MANIFEST = "assets/manifest.ron"           # where content keys live
KEY_PATTERN = r'"([a-z_]+\.[a-z0-9_]+)"'    # a manifest key inside a Rust string literal
KEY_SOURCES = ["crates", "game", "tests"]   # folders whose Rust code may name keys
RUNTIME_KEYS = set()                        # keys code builds at run time (prefix + name)
REQUIRED = ["workspace", "content"]         # non-crate boundaries the repo must have
KEYS = ["boundary", "package", "owns", "shares", "depends", "external", "dev-depends",
        "forbidden", "never-in-tree", "contract"]
BOUNDARY_SECTIONS = ["## Scope", "## Provides", "## Uses", "## Invariants", "## Tests",
                     "## Reading order"]
ROOT_SECTIONS = ["## Boundaries", "## Context", "## Parallel work", "## Integration suite",
                 "## Agent file format"]
AGENTS_OWN = (".hermes/", ".claude/")  # agents' own files: never owned, never a scope leak
LINE_LIMIT = 100
HERMES_BUDGET = 20_000  # characters of one AGENTS.md chain that Hermes loads in full, at least
problems, notes = [], []


def read(path):
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def git(*args):
    return subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT),
                           *args], capture_output=True, text=True, check=True).stdout


repo_files = {line for line in git("ls-files", "--cached", "--others", "--exclude-standard")
              .splitlines() if line and not line.startswith(AGENTS_OWN)}
agent_files, claude_files = {}, {}
if IN_PLACE:
    for name in sorted(f for f in repo_files if PurePosixPath(f).name == "AGENTS.md"):
        agent_files[name] = read(ROOT / name)
        claude = str(PurePosixPath(name).with_name("CLAUDE.md"))
        if (ROOT / claude).is_file():
            claude_files[claude] = read(ROOT / claude)
else:
    for draft in sorted(DRAFTS.rglob("AGENTS.draft.md")):
        agent_files[draft.relative_to(DRAFTS).with_name("AGENTS.md").as_posix()] = read(draft)
    shim = DRAFTS / "CLAUDE.shim.draft.md"
    if shim.is_file():
        claude_files = {str(PurePosixPath(f).with_name("CLAUDE.md")): read(shim)
                        for f in agent_files}
files = repo_files | set(agent_files) | set(claude_files)


def parse(file, text):
    """Front matter as {key: [values]}; None for a guide without front matter."""
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end < 0:
        problems.append(f"{file}: the front matter is not closed")
        return None
    b = {k: [] for k in KEYS}
    b["file"], key = file, None
    for line in text[4:end].splitlines():
        line = line.split("#", 1)[0]  # no path, crate or item name contains '#'
        if not line.strip():
            continue
        if line[0] in " \t":
            values = line
        else:
            key, _, values = line.partition(":")
            key = key.strip()
        if key not in KEYS:
            problems.append(f"{file}: unknown key {key}")
            continue
        b[key] += [v.strip() for v in values.split(",") if v.strip()]
    b["name"] = ",".join(b["boundary"])
    b["package"] = b["package"][-1] if b["package"] else None
    return b


boundaries = [b for file, text in agent_files.items() if (b := parse(file, text))]
if not boundaries:  # an empty set would make every check below pass
    sys.exit(f"no agent file with front matter in {DRAFTS}")
print("boundaries:", ", ".join(b["name"] for b in boundaries))


def matches(entry, path):
    return path.startswith(entry) if entry.endswith("/") else path == entry


def owner(path):
    """The boundary whose longest `owns` entry matches path."""
    best = None
    for b in boundaries:
        for entry in b["owns"]:
            if matches(entry, path) and (best is None or len(entry) > best[0]):
                best = (len(entry), b)
    return best[1] if best else None


def section(text, name):
    """Keys of one manifest section (`foo = ...`, `foo.workspace = true`, `foo = { ... }`)."""
    keys, inside = set(), False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("["):
            inside = line == f"[{name}]"
        elif inside and line and not line.startswith("#"):
            keys.add(re.split(r"[=. ]", line, maxsplit=1)[0])
    return keys


# Dependencies against the manifests.
root_toml = read(ROOT / "Cargo.toml")
start = root_toml.index("members = [")
members = re.findall(r'"([^"]+)"', root_toml[start:root_toml.index("]", start)])
if not members:  # search for ] from `members = [`, not from the start of the file
    sys.exit("no workspace members found in Cargo.toml")
packages = {}
for member in members:
    text = read(ROOT / member / "Cargo.toml")
    packages[re.search(r'^name = "([^"]+)"', text, re.M).group(1)] = (member, text)
for name, (path, text) in packages.items():
    b = next((b for b in boundaries if b["package"] == name), None)
    if not b:
        problems.append(f"{path}: no boundary has package {name}")
        continue
    deps, dev = section(text, "dependencies"), section(text, "dev-dependencies")
    for what, actual, declared in [("depends", deps & set(packages), b["depends"]),
                                   ("external", deps - set(packages), b["external"]),
                                   ("dev-depends", dev, b["dev-depends"])]:
        if actual != set(declared):
            problems.append(f"{path}: {what} is {sorted(actual)}, the file says {sorted(declared)}")
    problems += [f"{path}: depends on forbidden {f}" for f in b["forbidden"] if f in deps | dev]
    if b["never-in-tree"]:
        tree = subprocess.run(["cargo", "tree", "--offline", "-e", "normal", "--prefix", "none",
                               "-p", name], cwd=ROOT, capture_output=True, text=True)
        crates = {line.split()[0] for line in tree.stdout.splitlines() if line.strip()}
        if not crates:
            problems.append(f"{name}: cargo tree printed nothing: {tree.stderr.strip()[:200]}")
        problems += [f"{name}: {n} is in its dependency tree" for n in b["never-in-tree"]
                     if n in crates]
problems += [f"no boundary named {n}" for n in REQUIRED
             if not any(b["name"] == n for b in boundaries)]

# Ownership.
claims = {}
for b in boundaries:
    for entry in b["owns"]:
        claims.setdefault(entry, []).append(b["name"])
problems += [f"{e} is claimed by {', '.join(o)}" for e, o in claims.items() if len(o) > 1]
for b in boundaries:
    problems += [f"{b['file']}: {e} matches no file" for e in b["owns"] + b["shares"]
                 if not any(matches(e, f) for f in files)]
orphans = sorted(f for f in files if owner(f) is None)
if orphans:
    problems.append(f"{len(orphans)} files have no owner, e.g. {orphans[:10]}")

# Sections, and a CLAUDE.md shim beside every agent file.
for b in boundaries:
    text, last = agent_files[b["file"]], -1
    for heading in ROOT_SECTIONS if b["file"] == "AGENTS.md" else BOUNDARY_SECTIONS:
        at = text.find(f"\n{heading}\n")
        if at < 0:
            problems.append(f"{b['file']}: no {heading}")
        elif at < last:
            problems.append(f"{b['file']}: {heading} is out of order")
        else:
            last = at
for file in agent_files:
    claude = str(PurePosixPath(file).with_name("CLAUDE.md"))
    if "@AGENTS.md" not in claude_files.get(claude, ""):
        problems.append(f"{claude}: missing, or it does not import @AGENTS.md")


def public_code(directory):
    """Every .rs file below directory, each up to its first #[cfg(test)], without comments."""
    sources = sorted((ROOT / directory).rglob("*.rs"))
    if not sources:
        problems.append(f"{directory}: no .rs files")
    lines = []
    for source in sources:
        for line in read(source).splitlines():
            if line.strip() == "#[cfg(test)]":
                break
            if not line.lstrip().startswith("//"):
                lines.append(line)
    return "\n".join(lines)


def is_public(code, item):
    """Name-level check: the item's last path segment is declared pub or re-exported."""
    name = re.escape(item.rsplit("::", 1)[-1])
    kinds = "fn|async fn|const fn|struct|enum|trait|const|static|type|mod"
    if re.search(rf"pub (?:{kinds}) {name}(?![A-Za-z0-9_])", code):
        return True
    word = rf"(?<![A-Za-z0-9_]){name}(?![A-Za-z0-9_])"
    return any(re.search(word, use) for use in re.findall(r"pub use [^;]*;", code))


# Contracts: public items, manifest keys, and every key that code names.
manifest_path = ROOT / MANIFEST
manifest_keys = set(re.findall(KEY_PATTERN, read(manifest_path))) if manifest_path.exists() else set()
named = set(RUNTIME_KEYS)
for folder in KEY_SOURCES:
    for source in (ROOT / folder).rglob("*.rs"):
        for line in read(source).splitlines():
            if not line.lstrip().startswith("//"):
                named |= set(re.findall(KEY_PATTERN, line)) & manifest_keys
for b in boundaries:
    if not b["contract"]:
        continue
    if b["package"] is None:
        problems += [f"{b['file']}: key {k} is not in {MANIFEST}" for k in b["contract"]
                     if k not in manifest_keys]
        missing = sorted(named - set(b["contract"]))
        if missing:
            problems.append(f"{b['file']}: the contract lacks keys that code names: {missing}")
        unused = sorted(set(b["contract"]) - named)
        if unused:
            notes.append(f"{b['file']}: no Rust code names {unused}")
        continue
    code = public_code(PurePosixPath(b["file"]).parent.as_posix() + "/src")
    problems += [f"{b['file']}: {i} is not public in its crate" for i in b["contract"]
                 if not is_public(code, i)]

# Links, line length, and what Hermes loads for one folder.
for file, text in {**agent_files, **claude_files}.items():
    base = PurePosixPath(file).parent
    for link in re.findall(r"\]\(([^)#\s]+)", text):
        if re.match(r"[a-z]+:", link):  # http:, https:, mailto:
            continue
        parts = []
        for part in (base / link).parts:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        target = "/".join(parts)
        if target not in files and not (ROOT / target).exists():
            problems.append(f"{file}: broken link {link}")
    for number, line in enumerate(text.splitlines(), 1):
        long_code = any(len(span) > 60 for span in re.findall(r"`([^`]+)`", line))
        if len(line) > LINE_LIMIT and not line.startswith("|") and not long_code:
            problems.append(f"{file}:{number}: {len(line)} characters")
root_size = len(agent_files.get("AGENTS.md", ""))
chains = {f: len(t) + (root_size if f != "AGENTS.md" else 0) for f, t in agent_files.items()}
largest = max(chains, key=chains.get)
print(f"Hermes loads at most {chains[largest]:,} characters, for {largest}")
problems += [f"{f}: with the root file {n:,} characters, over {HERMES_BUDGET:,}"
             for f, n in chains.items() if n > HERMES_BUDGET]

# Drafts only: nothing of the root CLAUDE.md gets lost when it moves into the root AGENTS.md.
old_claude = ROOT / "CLAUDE.md"
if not IN_PLACE and old_claude.is_file() and "AGENTS.md" in agent_files:
    old = read(old_claude)
    if "@AGENTS.md" not in old:
        kept = set(agent_files["AGENTS.md"].splitlines())
        notes += [f"CLAUDE.md line not in the root AGENTS.md: {line.strip()[:90]}"
                  for line in old.splitlines() if line.strip() and line not in kept]

print(f"{len(files)} files, {len(boundaries)} boundaries, {len(named)} keys named by code")
for note in notes:
    print("note:", note)
print("\n".join(problems) if problems else "agent files pass every check")
sys.exit(1 if problems else 0)
