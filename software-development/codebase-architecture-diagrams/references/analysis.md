# Analysing a codebase for architecture diagrams

Every box, arrow and number on a page must come from the code or from a command, never from
memory. Collect the facts first; draw afterwards.

## Orientation
- Read the README, architecture docs, contributor rules (CLAUDE.md, AGENTS.md, CONTRIBUTING),
  every package manifest, the CI configuration and toolchain pins.
- List tracked files with `git ls-files`; never glob the tree, build output floods the results.
- In repos under about 10k lines, read every source file. The interface matrix and the
  improvement points come from reading call sites, not from matching names.

## Facts per page

| Page | Facts | Where they come from |
|---|---|---|
| overview | packages, internal dependency edges, external dependencies, lines and tests per package, the project's rules | manifests; line counts over `git ls-files <dir>`; the test runner's per-package summary; contributor rules |
| modules and API | modules per package, public or private, the public types and functions | module declarations and exports (`pub mod`, `__init__`, `index.ts`), public items, re-exports |
| interfaces | for each (user, provider) pair, what the user really calls | the user's imports of the provider, then each call site |
| runtime lifecycle | entry point, main loop, scheduling order, what runs per tick or request | `main`, the event loop, schedulers, routers, middleware chains |
| subsystem pipeline | stages in order, the data handed between them, state kept across iterations | the subsystem's top-level function, followed call by call |
| content or data pipeline | offline tools, file formats, registries or manifests, loaders, consumers | tool folders, build scripts, asset or schema folders, loader APIs |
| application layer | startup sequence, registered handlers or systems, what gets created | `main`, the app factory or plugin |
| improvement register | findings with evidence | the review below |

Commands that produce the numbers (adapt the paths):
- Lines per package: `git ls-files <dir> | xargs wc -l | tail -1`.
- Tests per package: the test runner's summary lines (cargo prints one
  `test result: ok. N passed` per crate, in workspace order).
- Bytes of tracked files: `git ls-files -z <dir> | xargs -0 cat | wc -c` (`du` over-reports on
  exFAT and other large-cluster drives).
- Dependency versions: the lockfile, not the manifest.
- Who imports a package: `search_files` for the package's name in the other packages' sources,
  then read the hits.

## Improvement points
Review while collecting facts. Each finding becomes one register entry:
- **ID**: `P` for process (backup, CI, releases), `N-xx` for near-term and small (a session or
  two each), `L-x` for later and larger (each needs its own plan). Reuse a plan's IDs if one
  exists, and keep them stable across pages and documents.
- **priority**: high (data loss, a visible bug, blocks other work), medium (cost or scaling),
  low (hygiene, things to watch).
- **where**: package · module, and a function when it helps.
- **finding**: what is wrong, with a number or path the reader could check.
- **proposal**: the fix, in one line.
- **short**: 30 characters at most; the badge note on the other pages.

Where findings come from:
- process: no off-machine copy, CI that never ran, an unpinned toolchain, an unchecked
  minimum version;
- measurement gaps: cost that is not logged, so optimisation would be guesswork;
- correctness: limitations the docs admit, invariants nothing checks;
- performance: per-frame or per-request work that grows with total size; brute-force loops;
- tests: paths with no automated check (rendering, I/O, UI);
- design debt: reusable code living in the application layer; duplicated constants;
- dead weight: features or dependencies nothing uses;
- upgrades to watch: pre-release major versions, ignored security advisories.

Mark each finding verified (a command showed it) or code-read. Only verified findings carry
numbers on the pages.

## Placing badges
Put each badge where its module appears: on the package node (overview), beside the module
(modules page), at the stage (lifecycle and pipeline pages), and once in the register. A
package with open points but no badge on a page that shows it is a review defect.
