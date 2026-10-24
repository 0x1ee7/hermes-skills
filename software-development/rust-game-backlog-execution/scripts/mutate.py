"""Mutation checks for guard tests: break one thing, run one crate's tests, restore.

    python mutate.py <crate> <mutations.json> [label ...]     (from the workspace root)

mutations.json is a list of {"label", "path", "old", "new", "test"}: `old` must occur exactly
once in `path`; it is replaced by `new`, `cargo test -q -p <crate> --lib -- <test>` must fail
("caught"), and the file is restored byte for byte and touched (on exFAT a restored file can
keep an mtime cargo takes as built). Ends with the crate's whole suite on the restored tree.
Exit 1 when a mutation is missed or does not compile, 2 when a pattern is not unique.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run_tests(crate, name_filter):
    result = subprocess.run(
        ["cargo", "test", "-q", "-p", crate, "--lib", "--", name_filter],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def touch(path):
    now = time.time() + 2
    os.utime(path, (now, now))


def main():
    crate, spec, *only = sys.argv[1:]
    mutations = json.loads(Path(spec).read_text(encoding="utf-8"))
    failures = 0
    for m in mutations:
        if only and m["label"] not in only:
            continue
        path = Path(m["path"])
        original = path.read_bytes()
        text = original.decode()
        if text.count(m["old"]) != 1:
            print(f"[{m['label']}] pattern found {text.count(m['old'])} times in {path}: STOP")
            return 2
        path.write_bytes(text.replace(m["old"], m["new"]).encode())
        touch(path)
        try:
            code, out = run_tests(crate, m["test"])
        finally:
            path.write_bytes(original)
            touch(path)
        compiled = "error[" not in out
        caught = compiled and code != 0 and "FAILED" in out
        status = "caught" if caught else ("MISSED" if compiled else "DID NOT COMPILE")
        if status != "caught":
            failures += 1
            print(out[-3000:])
        print(f"[{m['label']}] {m['test']}: {status}")
    code, out = run_tests(crate, "")
    print("restored:", code, [l for l in out.splitlines() if l.startswith("test result")])
    return 1 if failures or code else 0


if __name__ == "__main__":
    sys.exit(main())
