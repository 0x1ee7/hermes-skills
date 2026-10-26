---
name: agents-md-boundary-system
description: "Use to give any repo per-area AGENTS.md files with owns, provides and invariants."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [agents-md, boundaries, ownership, contracts, monorepo, parallel-agents]
    related_skills: [agent-context-files, parallel-agent-boundaries, agent-referee-checks, parallel-agent-task-protocol]
---

# AGENTS.md boundary system (any stack)

A repo is cut into **boundaries**. Each has one `AGENTS.md` saying what it owns, what it promises
others, what must stay true, and how to test it. A root `AGENTS.md` holds what applies everywhere
(commands, rules, the map, the parallel-work protocol). Nothing here depends on Cargo: a boundary
can be a package, a service, a folder of content or the CI config. For the Cargo recipe see
`parallel-agent-boundaries`; for tool loading rules see `agent-context-files`.

## When to Use
- Setting up a repo for several agents, or adding a boundary to one set up this way.
- An agent keeps editing code it does not own, or two agents collide on one file.
- Not for the text of the rules (the project decides) or for running the tasks
  (`parallel-agent-task-protocol`).

## Model
1. **Boundary** = a name plus the files it owns. Every tracked file has exactly one owner.
   Always add three non-code boundaries: `content`/`assets` (data and its generators),
   `workspace` (root files, docs, CI; the integrator's) and `integration` (the referee tests).
2. **Ownership resolution**: an `owns` entry ending in `/` owns the folder; otherwise one file.
   The longest matching entry wins; equal-length matches are an error. `shares` entries are
   editable without being owned (a design doc several boundaries touch).
3. **Contract** = public items that other boundaries actually use (grep for users; do not list
   everything public). Adding to a contract is free. Removing, renaming or changing meaning is an
   *interface change*, done only by the integrator, across every user, in one commit.
4. **Dependency direction is one-way**; each file lists `depends`, `forbidden` (never a direct
   dependency) and `never-in-tree` (not even transitively). The referee checks these.
5. **Interface request**: an agent that needs something from another boundary does not edit it.
   It writes boundary, need, why and proposed signature in its hand-off.

## Front matter (read by tests and `scripts/scope_check.py`)
```
---
boundary: name                 # the name AGENT_SCOPE uses
package: pkg                   # optional, the build system's name
owns: path/to/dir/             # trailing / = everything below
shares: docs/design.md
depends: a, b                  # internal dependencies
external: lib1, lib2           # third-party dependencies
forbidden: x, y
never-in-tree: z
contract: Item, Item::method   # or manifest keys for content
---
```
Comma lists; `#` starts a comment; a line starting with a space continues the key above.

## Sections, in order
**Scope**, **Provides**, **Uses**, **Invariants**, **Tests**, **Reading order** (extras between).
- Invariants each name the test that guards them; known issues use the project's tracker IDs.
- Reading order gives each file's size in lines (from `wc -l`, never guessed).
- No tutorials, no work in progress, no item IDs of open tasks (they go stale).
- Root file additionally: Commands, Rules (numbered), Boundaries table (name, file, owns, uses),
  Context (what to load and what to skip), Parallel work, Agent file format. Keep root plus the
  largest boundary file under the tool's context cap (20,000 chars is the safe floor).
- Each `CLAUDE.md` is a shim importing the `AGENTS.md` beside it (`@AGENTS.md`).

## Procedure
1. Inventory members, non-code areas, rules and line counts (`git ls-files <dir> | xargs wc -l`).
2. Draw boundaries; run `python scripts/scope_check.py owners` until it prints `ok`.
3. Write the root file, then one file per boundary, then the shims.
4. Add the referee (`agent-referee-checks`) so the files cannot rot.
5. Keep each file true in the same change as the code it describes.

## Pitfalls
- A new boundary without its `AGENTS.md`, shim and root-table row: the referee must fail.
- Rules left only in `CLAUDE.md` vanish for tools that read `AGENTS.md` first.
- An empty discovered set makes every check pass; assert non-empty.
