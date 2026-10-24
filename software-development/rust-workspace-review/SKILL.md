---
name: rust-workspace-review
description: "Use when auditing a Rust/Cargo workspace for upgrades."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [rust, cargo, code-review, msrv, clippy, wgpu, bevy_ecs, game-engine]
    related_skills: [codebase-inspection, requesting-code-review, parallel-agent-boundaries]
---

# Rust workspace review ("what needs upgrading / touching up")

Read-only audit: baseline gates, MSRV/dependency checks, docs lint, engine pitfalls.
Gather evidence with real commands; every finding gets a path:line.

## When to Use
- "Analyze the codebase / what needs upgrading / touch-ups" on a Cargo workspace.
- Pre-release or pre-phase health check of a Rust project (especially wgpu/winit/bevy_ecs engines).
- Skip for reviewing a single diff (use requesting-code-review).

## 1. Orientation
- Read README, CLAUDE.md/AGENTS.md, docs/architecture*, root Cargo.toml, rust-toolchain.toml, CI yaml.
- List tracked files with `git ls-files` (never glob the tree: `target/` floods results).
- Small repos (< ~5k LOC): read every source file; findings come from reading, not grepping.

## 2. Baseline gates (run in background, write logs to an absolute scratch path, then summarise)
Spell the scratch path out in background commands: they don't inherit exported variables, and an
empty `$TMPDIR` sends the logs to `/`.
```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
cargo doc --no-deps --workspace 2>&1 | grep -A3 'unresolved link'   # broken intra-doc links
cargo deny check                                                      # when deny.toml exists
```

## 3. Checks that found real issues
- **default-members trap**: if `default-members` is set, plain `cargo test` only tests those
  members. Verify with `cargo test 2>&1 | grep 'test result'` and flag docs that say otherwise.
- **MSRV**: `rust-version` in `[workspace.package]` is dead unless each member has
  `rust-version.workspace = true`. Compare with deps' MSRV:
  `grep -m1 '^rust-version' ~/.cargo/registry/src/*/<crate>-<ver>/Cargo.toml`.
  Language features to grep for: let-chains `&& let` need 1.88 (edition 2024).
- **Missing docs** without rebuilding deps (flags after `--` only hit workspace crates):
  `cargo clippy --workspace --all-targets -- -W missing_docs 2>&1 | grep '^warning: missing documentation for' | sort | uniq -c`
  Report the count excluding struct fields/variants separately.
- **Latest versions**: `curl -s -A 'review (local)' https://crates.io/api/v1/crates/<name>` -> `crate.max_stable_version`.
  Versions from Cargo.lock: `awk '$0=="name = \"<name>\"" {getline; print $3}' Cargo.lock`.
- **Duplicates**: `cargo tree -d --workspace --depth 0 -e normal`. Cargo.lock can list optional deps
  that are never built (e.g. bevy_reflect -> older glam); confirm with `cargo tree -i <pkg>@<ver> --target all -e all`
  before claiming a duplicate.
- **Advisories**: if `cargo deny check` fails and no dependency changed, the cause is usually
  a new RUSTSEC entry.
  - Find what pulls the crate in with `cargo tree -i <crate> --target all -e all --locked`.
  - Deny reads every target in the lockfile unless `[graph] targets` narrows it. A crate pulled
    in only by a wasm backend therefore still fails native CI.
  - Propose `cargo update -p <crate>` (a commit that changes only the lockfile) rather than an
    ignore. An ignore needs a `reason`.
- LICENSE files present when Cargo declares `MIT OR Apache-2.0`?
- **Backup and CI reality**: `git remote -v` plus the ahead count from `git status`. A remote
  that is a bundle file (fetch-only) or a long unpushed history means no off-machine copy and
  a CI workflow that has never run on that work; report it first, and never push unasked.
- Toolchain `channel = "stable"` + CI `-D warnings` = CI breaks on new clippy lints; recommend pinning.

## 4. Game-engine checklist (wgpu / winit / bevy_ecs style projects)
- Fixed timestep: is the interpolation alpha actually read by rendering? If not -> judder above 60 Hz.
  Also look for camera/rotation state mutated in the fixed schedule.
- winit `ControlFlow::Poll` + unconditional `request_redraw` + renderer returning early on
  Occluded/Outdated/zero-size = busy loop when minimized.
- Textures with `mip_level_count: 1` + perspective/zoom-out camera = shimmer.
- Normals transformed by the model matrix while Transform allows non-uniform scale.
- `world.query()` built every frame in extraction -> cache `QueryState`.
- glTF skin import: only first skinned node? non-joint ancestor (Armature) transforms dropped?
  joint indices validated? panics (assert) that bypass a documented fallback path?
- Settings resources defined in the render crate but needed by game crates that must not depend on it.
- Window size in PhysicalSize instead of LogicalSize (tiny window on HiDPI Windows).
- Hard-coded lighting/orientation constants duplicated across crates (inconsistent light directions).
- Time: elapsed seconds in f32 (millisecond steps after a few hours), or a dt clamp applied only
  to the fixed-step accumulator (frame systems still see the whole stall).
- Docs promise a deterministic simulation, but the fixed schedule has no ambiguity detection and
  runs on the multi-threaded executor. For schedules this small the single-threaded one is also
  ~50x faster per update.
- Renderer setup: `Limits::default()` instead of the adapter's limits, no uncaptured-error
  handler (wgpu panics), a hard-coded present mode, `cull_mode: None` left over from asset
  bring-up.
- Text formats parsed with `filter(|l| !l.trim().is_empty())` silently drop meaningful blank
  rows (e.g. maps where a space means "nothing").

## 5. Windows / exFAT pitfalls
- `fatal: detected dubious ownership` on drives without ownership (exFAT): use
  `git -c safe.directory='D:/path' <cmd>` per command; do not edit global git config unasked.
- "hard linking files in the incremental compilation cache failed" warnings are filesystem noise,
  not code warnings; suggest `CARGO_TARGET_DIR` on NTFS.
- A windowed smoke test (`ISO_EXIT_AFTER_FRAMES=N cargo run` style) opens a window briefly; fine to run.
- `du -sh` over-reports on exFAT (cluster size: 1.2 MB of models showed as 16 MB). Measure
  tracked bytes with `git ls-files -z <dir> | xargs -0 cat | wc -c`.

## 6. Report shape
Plain text in CLI. Baseline line (gates, tests, deps current?), then priority groups:
correctness/feel -> design debt -> small touch-ups -> CI/tooling -> environment aside.
Say which findings are code-read vs measured. Offer to implement the small contained fixes first.

## 7. Handoff file (when the user wants another agent to resume)
- Write `docs/upgrade-backlog.md` (untracked; don't commit unasked). Keep the chat's item numbers.
- Top: snapshot (commit, baseline gate results, dep versions), evidence legend
  ([verified] / [code-read]), checklist with stable IDs, machine quirks, open decisions for the
  user, suggested batches with ordering dependencies, out-of-scope list, append-only work log.
- Per item: Where (path:line), Problem, Fix, Pitfalls, Done when (testable acceptance).
- Before finishing, print every cited path:line with `sed -n "${l}p"` in a loop and check each
  one; line references are what the next agent relies on.
- Flag APIs newer than training data and tell the next agent to read the local registry source
  (`~/.cargo/registry/src/*/<crate>-<ver>/`) instead of writing calls from memory.
