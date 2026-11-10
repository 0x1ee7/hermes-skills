---
name: mutation-graded-test-exercises
description: "Use for exercises where the learner writes tests graded by mutants; not for ordinary unit tests."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [testing, mutation-testing, exercises, grading, pytest, go, ctest, cargo]
    related_skills: [tdd-exercise-repo-harness, verify-the-check]
---

# Mutation-graded "write the tests" exercises

The learner owns a test suite; the repo owns production code and a grader. The grader runs the
suite against the original (must pass) and against each mutant (must fail). Built in Python, Go,
C++ and Rust with 20-24 mutants each.

## When to Use
- A "unit testing" topic in an exercise repo (`tdd-exercise-repo-harness`).
- Checking that an existing suite actually guards specific behaviours.

## Design
1. **Production code that needs real testing skill**: money in integer cents with rounding,
   tiered discounts at boundaries, a service with injected gateway/notifier/clock/sleeper doing
   retry with exponential backoff, logging at specific levels, an atomic file export. Some
   behaviour must be observable only through fakes/mocks (sleep durations, call args, frozen
   clock, captured logs, temp dirs).
2. **Real sleeps in the default path** (the production `Sleeper` sleeps seconds) plus a grader
   time budget: forces the learner to inject a fake.
3. **Mutants are explicit text replacements**, each asserted to match exactly once (fail the
   grader setup otherwise: a replacement that matches nothing is a silent no-op). Name them;
   the README lists only categories (rounding, boundaries, tax base, retry classification,
   backoff, log level, receipt failure handling, temp-file cleanup, UTC...), not the edits.
4. **Grader tests**: `baseline` (suite passes on the original and has >= N tests; parse the
   runner's count), one test per mutant (suite must fail), `time_budget`.
5. **Placeholder suite must fail every grader test**: an empty suite fails the baseline by count
   (or pytest exit code 5); mutant tests fail because nothing failed.
6. **Reference suite** in `solutions/` kills all mutants: fixtures, parametrization, fakes over
   deep mocks, a property test, temp dirs.

## Per-language recipe
- **Python**: copy the learner's `main.py` as `test_student.py` next to a (mutated) copy of the
  module in `tmp_path`; run `sys.executable -m pytest -q -p no:cacheprovider` with `cwd` there
  and an empty `-c` ini / `--rootdir` so the repo's pyproject/conftest are not loaded.
- **Go**: provided code as a subpackage; learner writes `suite/suite_test.go`. Per run, build a
  temp module (`go.mod` + copied package with rewritten import path + the suite) and run
  `go test -count=1 -json` with `GOWORK=off`, `GOFLAGS` cleared, the toolchain from `GOROOT`
  (not PATH). Run mutants with bounded concurrency. The suite file is a `_test.go`, so a
  solutions overlay doesn't swap it: locate it via the exercise-dir helper.
- **C++/CMake**: at configure time `file(READ)` + `string(REPLACE)` + `file(WRITE)` per mutant
  (FATAL_ERROR if the pattern count is not 1); one test executable per mutant linking the
  learner's suite; ctest `Grader.mutant_<name>` with `WILL_FAIL TRUE`; baseline checks
  `--gtest_list_tests` count via a CMake script. Keep provided code out of the engineer-owned
  glob (subdirectory). Mutant copies may emit warnings; that is expected.
- **Rust**: grader integration test generates throwaway crates (`src/lib.rs` = mutated code,
  `tests/suite.rs` = learner suite) and runs `cargo test --offline` with `CARGO_TARGET_DIR`
  set to its own dir (the outer cargo holds the build lock: same dir deadlocks). Give each scratch
  crate a unique package name and `[lib] name = "<original>"`, or a stale binary from another
  mutant gets run. Read provided code with `include_str!` relative to the grader.

## Verification
- Placeholder suite: every grader test fails.
- Reference suite: baseline passes, every mutant killed, within the budget. Report total runtime
  (15-50 s is typical).
- Each mutant's replacement was seen to apply (grader asserts the match count).
