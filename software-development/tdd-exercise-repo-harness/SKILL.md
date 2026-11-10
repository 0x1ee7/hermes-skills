---
name: tdd-exercise-repo-harness
description: "Use for test-driven exercise repos (Python, Go, C++, Rust) with stubs and a solutions switch; not for example code without tests."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [exercises, kata, tdd, test-harness, python, go, cpp, rust, education]
    related_skills: [mutation-graded-test-exercises, verify-the-check, subagent-path-and-broadcast-hygiene, parallel-agent-task-protocol]
---

# Test-driven exercise repo harness

Layout and grading switch for "make the failing tests pass" repos. Built four times (pyref,
goref, cppref, rustref; ~80 topics, ~7,000 test cases). Each repo: `exercises/<NN_topic>/`
(spec README, engineer-owned entry point, tests) and `solutions/<NN_topic>/` (reference answer),
graded by the same tests.

## When to Use
- Building practice/refresher material, coding-interview prep, onboarding katas.
- Not for one-off example code without tests.

## Requirements (all languages)
1. One unimplemented function fails only its own tests: no collection errors, no aborting the
   whole test binary, no hangs.
2. With the starting code, every test fails: 0 pass, 0 skip. With `--solutions`-style mode, all pass.
3. The same test files grade both trees; never duplicate tests into `solutions/`.
4. Tests black-box the public API, named by part (`Part2...`) so one part can be selected.
5. README per topic = spec: scenario, parts with exact API and edge cases, concepts, run commands,
   untested stretch ideas. Real-world scenarios, not puzzles.

## Per-language recipe

**Python (pytest).** `main.py` holds only a docstring. A root `conftest.py` fixture `main`
imports a fresh copy per test (`importlib.import_module("main")` after purging modules from
`exercises/`/`solutions/` and `monkeypatch.syspath_prepend(workdir)`), so missing names fail per
test and module state never leaks. Register it as `sys.modules["main"]` with the dir on
`sys.path` so functions pickle into `ProcessPoolExecutor` (spawn) workers. `--solutions` option
switches `workdir`; also expose `exercise_dir` for provided assets. Use `--import-mode=importlib`,
`pytest-timeout`. Purge check must be cheap (string-prefix on `os.path.normcase`, not
`Path.resolve()` per module).

**Go.** Tests must compile, so ship stubs declaring the exported API with zero-value bodies.
Stubs must not panic or block: a panic or deadlock kills the whole test binary. Grade solutions
with `go test -overlay=<json>` mapping each `exercises/<t>/<f>.go` to `solutions/<t>/<f>.go`
and `""` (hide) for exercise files the solution lacks; a `go run ./tools/solutions` wrapper writes
the overlay and sets `GOREF_SOLUTIONS=1`. Put a `go.mod` in `solutions/` so `go build ./...`,
`go vet ./...` and gopls skip it (solution files may import exercise `internal/` packages, which
only resolves under the overlay). Overlays don't affect runtime file reads: give tests a helper
(`exercise.Dir(t)`) to find engineer-owned non-Go files (Dockerfile).

**C++ (CMake + GoogleTest).** Headers declare the API; definitions
`throw std::logic_error("not implemented: X")` (gtest reports per test). A `cppref_exercise()`
function globs: `*_test.cpp`/`*_test.hpp` are tests, every other `.hpp/.cpp` is engineer-owned and
taken from `solutions/<t>/` when `-DCPPREF_SOLUTIONS=ON`. Trap: `#include "x.hpp"` searches the
including file's directory first, so tests compiled in place pick up the exercise stub header
even in solutions mode; compile copies of the tests from the build tree in solutions mode.
`gtest_discover_tests(... DISCOVERY_MODE PRE_TEST TEST_PREFIX "<t>.")`. Presets `dev`/`solutions`
plus workflow presets. Add `-DCPPREF_ONLY=<t>` so parallel builders configure one topic.

**Rust (cargo).** `src/lib.rs` declares the API with `todo!()` bodies (panic = one failed test);
tests are integration tests in `tests/`. Solutions are a second workspace (`solutions/Cargo.toml`,
members `[0-9][0-9]_*`, excluded from the root) whose crates share the package name, set
`autotests = false` and point `[[test]] path = "../../exercises/<t>/tests/<f>.rs"`. Alias
`cargo solutions = "test --manifest-path solutions/Cargo.toml --target-dir target"` shares
`target/`. Traps: `todo!()` in `-> impl Trait` position does not type-check; `const fn` cannot
contain `todo!()` (use `panic!("literal")`); stubs that keep serde derives or other derived impls
let tests pass vacuously; assets via `include_str!` relative to the test file.

## Procedure
1. Write the harness and prove it with a throwaway smoke topic in both modes (fail/pass), then
   delete it.
2. Pre-fetch shared dependencies once (pip/uv sync, `go get`, gtest source dir reused via
   `FETCHCONTENT_SOURCE_DIR_GOOGLETEST`, a warm-up crate depending on every workspace dep) so
   parallel authors don't fight over manifests or recompiles.
3. Author topics (in parallel if many: one agent per topic, owning only its two dirs; see
   `subagent-path-and-broadcast-hygiene`).
4. Per topic: stub run has 0 passes; solutions run is all green (3-5x for concurrency/timing).
5. Whole-repo run of both modes in one process/build to catch leaks between topics.
6. Root README: setup, workflow, how the harness works, index table generated from topic
   READMEs (title + part headings + counts). Wrap `<T>`-style tokens in backticks in tables.

## Verification
- Stub mode: summary shows 0 passed (Go: zero `pass` actions in `-json`).
- Solutions mode: 0 failed, and repeated runs green for timing-sensitive topics.
- Every "passes against stubs" case fixed by a positive control, not by deleting the test
  (`verify-the-check`).
