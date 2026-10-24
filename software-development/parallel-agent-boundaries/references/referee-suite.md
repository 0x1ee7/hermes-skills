# Referee suite (Cargo workspace)

The referee is a workspace member that every agent runs and only the integrator changes. It
checks rules and contracts between crates; each crate's own tests cover its behaviour.

## Layout

```
tests/integration/
  Cargo.toml           publish = false; dev-dependencies on every crate it drives,
                       never the window/platform crate (it must run without a window)
  src/lib.rs           helpers, standard library only: workspace root, manifest sections,
                       agent-file front matter, ownership, source scanning, git changes
  tests/suite/main.rs  mod architecture; mod boundaries; mod scope; mod pipeline; mod levels;
```

Put every test in one binary, as modules of `tests/suite/main.rs`, so it links once. Each file
directly under `tests/` would be a separate binary.

## Checks

Write one test per rule and name it after the rule.

| Part | Fails when | Approach |
|---|---|---|
| architecture | a crate's dependency sections differ from its agent file, or name a forbidden crate | read the keys of `[dependencies]` and `[dev-dependencies]`; a key ends at `=`, `.` or a space (`foo.workspace = true`) |
| architecture | a lower crate pulls in a `never-in-tree` crate transitively | `cargo tree -e normal --prefix none -p <pkg>`, first word of each line; assert the output is non-empty |
| architecture | a member does not inherit a dependency, a package field or the lints from the workspace | `workspace = true` on every dependency, `x.workspace = true` fields, `[lints] workspace = true` |
| architecture | the renderer writes to the world | look for the ECS's mutating calls in the renderer's non-test code, and for `World` named outside the files allowed to see it |
| architecture | code names an asset file instead of a manifest key | look for asset file paths in string literals outside the asset crate |
| architecture | camera or projection maths appears outside the maths crate | look for matrix and projection construction outside that crate |
| boundaries | a member or area has no agent file | take the members from the root manifest (assert non-empty) and add the non-crate boundaries |
| boundaries | a section is missing or out of order, or the `CLAUDE.md` beside an agent file does not import `@AGENTS.md` | match headings as whole lines |
| boundaries | a file has no owner or two, or an `owns` entry matches nothing | list tracked and untracked-but-not-ignored files, minus `.hermes/` and `.claude/`; a trailing `/` owns a subtree, otherwise one file; the longest entry wins |
| boundaries | a contract item is not public | the item's last path segment must be declared `pub`, or re-exported by `pub use`, in non-test code; content keys must be in the manifest |
| boundaries | the front-matter parser reads lists, continuations or `#` comments differently from the root file's description | parse a literal agent file; also a pointer file without front matter (`Ok(None)`) and an unknown key (an error) |
| boundaries | a referee test is missing from the referee's own agent file | each `#[test]` function in `tests/suite/*.rs` must appear as `` `module::name` `` in `tests/integration/AGENTS.md` |
| scope | a change since `AGENT_BASE` lies outside `AGENT_SCOPE` | changes = `git diff --name-only --no-renames <base>` plus `git ls-files --others --exclude-standard`; each must be owned or shared by a boundary in scope; `*` allows everything; unset skips the check; an unknown boundary name fails and lists the known ones |
| pipeline | a contract between crates breaks | use public APIs only: the interpolated position reaches the draw list; skinned palettes have the identity plus one matrix per joint; a broken texture key reaches the renderer as the stand-in |
| levels | a level warns while loading, or its scripted tour breaks an invariant | load every level key; walk, run, turn the view and switch cameras with fixed frame times; list every broken invariant in one message |
| levels | the simulation depends on the frame rate | run the same fixed steps at 30, 60 and 144 fps and compare the results bit for bit |

`--no-renames` reports both paths of a move, so both must be in scope. `AGENT_BASE` defaults to
`HEAD`, which checks only uncommitted changes.

## Recipes

- **Source scans.** Read each `.rs` file below a crate's `src/` up to its first `#[cfg(test)]`,
  and skip comment lines, so test helpers and docs don't trip the rules. Assert that the file
  list is non-empty, so a moved folder fails instead of passing.
- **Git.** Run git from the helper as `git -c safe.directory=<root> ...`. Plain git refuses to
  work on drives without ownership (exFAT).
- **Warnings.** Install one `log` logger that records into a thread-local buffer. `set_logger`
  succeeds only once per process, so guard it with `std::sync::Once`. Tests run on parallel
  threads, and each must see only its own warnings.
- **Entity counts.** For "nothing spawned or lost" checks, take the baseline after one warm-up
  update: ECS frameworks create their bookkeeping lazily. For bevy_ecs, see
  `rust-game-backlog-execution`, `references/engine-recipes.md`.
- **Headless and repeatable.** No window, no GPU, no network and no sleeps; fixed frame times
  and seeded randomness. The renderer's extraction runs on the CPU through its public
  extractor, so draw lists and palettes can be tested without a device. Check that the world is
  unchanged afterwards.
- **Frame-rate independence.** Drive the same app at several frame times and compare the state
  after the same number of fixed steps, exactly. A difference means a fixed system reads the
  frame time, or randomness is unseeded.
- **Several test filters.** Cargo takes one filter before `--`, libtest several after it:
  `cargo test -p integration_tests --test suite -- boundaries:: architecture::crate`. A second
  filter before `--` is an error, easy to miss when the output is piped through `grep`.
- **Guides are files too.** Tools that list a content folder (asset lists, orphan checks) see a
  new `AGENTS.md` or `CLAUDE.md` there. Run every generator's `--check` after adding guides,
  and leave Markdown out of such scans.
