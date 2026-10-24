"""Show what Hermes loads as project context for a folder, and what its injection scanner would
change in a file, using Hermes's own code (agent/prompt_builder.py).

Usage:
  python3 check_context_files.py load <folder>... [--expect TEXT]...
  python3 check_context_files.py scan <file>...

Any Python 3 will do: when Hermes's modules are not importable, the script asks
`hermes --print-runtime-command` for Hermes's interpreter and source folder and runs itself
again there. Exit status 1 when a folder loads nothing, is truncated, has blocked text or lacks
an --expect text, or when the scanner would change a file. It uses Hermes internals
(discover_context_files, build_context_files_prompt, _scan_context_content); if an import fails
after a Hermes update, look the names up in agent/prompt_builder.py.
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RELAUNCHED = "CHECK_CONTEXT_FILES_RELAUNCHED"


def relaunch():
    """Run this script again under Hermes's own interpreter, with its source on sys.path."""
    hermes = shutil.which("hermes")
    if os.environ.get(RELAUNCHED) or not hermes:
        sys.exit("Hermes's modules are not importable, and `hermes` is not on PATH to find them")
    result = subprocess.run([hermes, "--print-runtime-command"], capture_output=True, text=True,
                            timeout=120)
    command = json.loads(result.stdout.strip().splitlines()[-1])
    python, code = command[0], command[-1]
    found = re.search(r"sys\.path\.insert\(0, ('(?:[^'\\]|\\.)*')\)", code)
    if not found:
        sys.exit("Hermes's runtime command does not name its source folder:\n" + code[:300])
    source = ast.literal_eval(found.group(1))
    script = str(Path(__file__).resolve())
    boot = (f"import sys, runpy; sys.path.insert(0, {source!r}); "
            "sys._hermes_pin_default_home = True; import hermes_bootstrap; "
            f"sys.argv = {[script, *sys.argv[1:]]!r}; "
            f"runpy.run_path({script!r}, run_name='__main__')")
    env = dict(os.environ, **{RELAUNCHED: "1"})
    sys.exit(subprocess.run([python, "-I", "-c", boot], env=env).returncode)


try:
    from agent.prompt_builder import (_scan_context_content, build_context_files_prompt,
                                      discover_context_files)
except ImportError:
    relaunch()


def load(folders, expects):
    """Report what a session started in each folder gets; return how many have problems."""
    failed = 0
    for folder in folders:
        cwd = Path(folder).resolve()
        found = discover_context_files(cwd)
        winner = next((kind for kind, _, _, content in found if content), None)
        text = build_context_files_prompt(cwd=str(cwd), skip_soul=True)
        print(f"{cwd}: {len(text):,} characters of project context")
        for kind, label, _, content in found:
            state = "empty" if not content else "loaded" if kind == winner else "shadowed"
            print(f"  {state:<8} {kind:<11} {label} ({len(content):,} chars)")
        problems = []
        if not text:
            problems.append("nothing loads")
        blocked = [line.strip() for line in text.splitlines() if "[BLOCKED" in line]
        if blocked:
            problems.append(f"{len(blocked)} line(s) blocked, e.g. {blocked[0][:120]}")
        if "[...truncated" in text:
            problems.append("truncated: shorten the files or move detail elsewhere")
        problems += [f"does not contain {e!r}" for e in expects if e not in text]
        for problem in problems:
            print("  PROBLEM:", problem)
        failed += bool(problems)
    return failed


def scan(files):
    """Print what the injection scanner would replace; return how many files it changes."""
    changed = 0
    for name in files:
        text = Path(name).read_text(encoding="utf-8")
        out = _scan_context_content(text, Path(name).name)
        if out == text:
            print(f"{name}: unchanged")
            continue
        changed += 1
        print(f"{name}: the scanner would change it")
        for line in out.splitlines():
            if "BLOCKED" in line:
                print("   ", line.strip()[:160])
    return changed


def main(argv):
    if len(argv) < 2 or argv[0] not in ("load", "scan"):
        sys.exit(__doc__)
    if argv[0] == "scan":
        return 1 if scan(argv[1:]) else 0
    folders, expects, args = [], [], iter(argv[1:])
    for arg in args:
        if arg == "--expect":
            expects.append(next(args))
        else:
            folders.append(arg)
    return 1 if load(folders, expects) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
