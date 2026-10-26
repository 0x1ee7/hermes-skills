"""Mutation checks for Python code: python pymutate.py <file> <mutations.json> <check.py>

Each entry {"label", "old", "new"} replaces `old` (exactly once) with `new` in <file>, runs
<check.py>, and reports "caught" when it exits non-zero; the file is restored byte for byte
after each. Exits 1 when a mutation is missed or the unmutated check fails. The check is a
script of its own that exits 1 on failure (a repo without a Python test suite: a level kit, a
generator)."""
import json
import subprocess
import sys
from pathlib import Path

target, mutations, check = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), sys.argv[3]
original = target.read_bytes()
missed = 0
try:
    for m in mutations:
        text = original.decode()
        if text.count(m["old"]) != 1:
            print(f"[{m['label']}] not found once ({text.count(m['old'])})")
            missed += 1
            continue
        target.write_bytes(text.replace(m["old"], m["new"]).encode())
        result = subprocess.run([sys.executable, check], capture_output=True, text=True)
        caught = result.returncode != 0
        print(f"[{m['label']}] {'caught' if caught else 'MISSED'}")
        missed += not caught
finally:
    target.write_bytes(original)
result = subprocess.run([sys.executable, check], capture_output=True, text=True)
print("restored:", "passes" if result.returncode == 0 else "FAILS")
sys.exit(1 if missed or result.returncode else 0)
