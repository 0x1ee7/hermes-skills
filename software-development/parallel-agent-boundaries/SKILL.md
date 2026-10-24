---
name: parallel-agent-boundaries
description: "Use when preparing a repo for parallel coding agents."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [agents, multi-agent, agents-md, claude-md, architecture-tests, integration-tests, cargo, git-worktree]
    related_skills: [agent-context-files, rust-workspace-review, rust-game-backlog-execution, codebase-architecture-diagrams, test-driven-development]
---

# Parallel agent boundaries

This skill makes a repository safe for several coding agents at once. Each agent works inside one
boundary: a crate, the app, or the content tree. The boundary's `AGENTS.md` says what it owns,
provides, uses and promises. Its front matter is read by tests and its sections by agents. A
root `AGENTS.md` holds the map and the protocol. A referee test package enforces three things:
the architecture rules, the agent files and each task's scope. It also plays the real app
headlessly. The method was worked out on a Cargo workspace (engine crates, a game, generated
content). The procedure carries over to other stacks; the recipes in `references/` are
Cargo-specific.

## When to Use
- Requests such as "get the repo ready for several agents working in parallel", "an AGENTS.md
  per crate" or "tests that enforce the architecture rules".
- Adding a boundary (a new crate) or changing the agent-file format in a repo set up this way.
- Not for a one-off CLAUDE.md edit, and not for handing a task to an agent CLI (use
  `claude-code` or `codex`).

## Support files
- `references/agent-file-format.md`: front matter keys, section order, the root file's outline
  and protocol, the hand-off note, the CLAUDE.md shim, and the writing style.
- `references/referee-suite.md`: the package layout, every check and how it is built, and the
  headless recipes.
- `templates/validate_agent_drafts.py`: checks agent files against the repo, as drafts before
  they are written or in place afterwards (`--in-place`): dependencies, owners, sections, shims,
  contracts and their completeness, never-in-tree crates, links, line length and the Hermes
  budget. Copy it and adapt the constants at the top.
- `agent-context-files` (another skill): which tool loads which file, the shim, and
  `check_context_files.py`, which shows what a Hermes session started in any folder gets.

## Procedure
1. Take an inventory, without changing anything. Collect:
   - the workspace members and their dependency sections;
   - the architecture rules (CLAUDE.md, README, architecture docs);
   - the non-code areas (assets, generators, docs, CI);
   - the project's improvement register, if it has one;
   - the line count of each area, tests included
     (`git ls-files <dir> | xargs wc -l | tail -1`).
   Done when every tracked file has an obvious owner.
2. Draw the boundaries. Make one per member, plus three more:
   - `content`: the assets and the tools that generate them;
   - `workspace`: the root files, docs and CI (the integrator's);
   - `integration`: the referee.
   Every file gets exactly one owner. A doc that several boundaries edit is listed under
   `shares`. A contract is what other boundaries actually use, so grep for the users rather than
   listing every `pub` item.
3. Make the app drivable without a window. Split the binary into a library (the plugin, level or
   scene loading, the choice of start level) and a thin `main.rs` that only opens the window.
   Run the smoke test after the split.
4. Build the referee package (`references/referee-suite.md`) as a workspace member, so that
   `cargo test --workspace` and CI run it.
5. Mutation-check every referee test before trusting it:
   1. Back the file up to scratch.
   2. Add one deliberate violation, such as a world write in the renderer, an asset path in game
      code, or a tolerance ten times too loose.
   3. See the test fail with a message that names the file and line, or the entity.
   4. Restore the backup and see the test pass.
6. Draft the agent files as `AGENTS.draft.md` under the workspace's `.hermes/agents-drafts/`,
   mirroring the repo layout (`references/agent-file-format.md`). Validate the drafts with the
   template. Then mutation-check the validator itself: drop a dependency from a draft, add an
   invented contract item, remove an `owns` entry. Each change must be reported. Then run
   Hermes's injection scanner over the drafts (`check_context_files.py scan`): one match would
   replace a whole file with a `[BLOCKED]` line.
7. Move the root `CLAUDE.md` into the root `AGENTS.md`: its intro, commands and rules go in
   word for word, and every `CLAUDE.md`, the root one included, becomes the shim. Hermes loads
   one kind of context file and an `AGENTS.md` wins, so rules left in `CLAUDE.md` would vanish
   from Hermes sessions without a warning. Write the agent files and shims in one approval
   batch. Check that each equals its draft (`cmp`), that every line of the old root `CLAUDE.md`
   is in the root `AGENTS.md` except lines reworded on purpose, and what Hermes loads from the
   root and from each boundary folder (`check_context_files.py load`). Then run the referee
   three times:
   - `cargo test -p integration_tests`: all green;
   - the same with `AGENT_SCOPE='*'`: all green;
   - once with a single boundary, to see the scope check list the files outside it and their
     owners.
8. Run every repo gate: fmt, clippy with `-D warnings`, tests, docs, smoke, and every
   generator's `--check`, since tools that list a content folder count the new guides as files.
   Point docs that call `CLAUDE.md` the home of the rules at `AGENTS.md`, and update the docs
   and diagrams that list the members. In the report, give each check with the violation it was
   seen failing on and anything still waiting for approval. Say that nothing is committed unless
   the user asked for it.
9. When asked to commit, follow the repo's commit rules. The agent files and the referee go in
   one commit, since each needs the other; the app split, tool fixes and diagrams go in earlier
   commits of their own. Gate each commit's exact tree first (`rust-game-backlog-execution`,
   "Committing a finished working tree as several commits").

## Rules
- Every write to an agent-instruction file (`AGENTS.md`, `CLAUDE.md`) may ask the user for
  approval, and an unanswered prompt times out. Do all other work first. Keep the validated
  drafts in `.hermes/`: scratch is pruned after a day idle, and the referee never counts
  `.hermes/` as a scope leak. Do the approval round in one batch while the user is there. Until
  then, name the referee tests that stay red. Agent-file edits that later work cannot get
  approved go into the queue's "Agent files" section, newer than the files, until one batch
  applies them (`agent-context-files`, Rules).
- Assert that every discovered set is non-empty before checking it: members, source files,
  levels, agent files. An empty set makes every check pass. For example, searching for the
  closing `]` from the start of the file instead of from `members = [` finds no members, and
  the referee then passes anything.
- Main stays green. A check that exposes a known bug lands as
  `#[ignore = "<improvement ID>: why"]`, and the fix removes the ignore.
- Failure messages name the file and line, or the entity, and say what to do. The reader is an
  agent with no context.
- Agent files carry contracts and invariants, not tutorials (`references/agent-file-format.md`).
  Numbers come from commands, every invariant names the test that guards it, and known issues
  use the project's improvement IDs.
- A boundary agent never edits the referee to make a change pass. An interface change is the
  integrator's task: the new signature, every caller and the referee's own calls go in one
  commit. Workspace files (`Cargo.toml`, `Cargo.lock`, CI, root docs) belong to the integrator
  too, so an agent that needs a new dependency files an interface request.
- A new crate gets its `AGENTS.md`, its shim and a row in the root table in the same change as
  its `Cargo.toml`. The boundaries tests fail until it has them.
- The setup task itself touches the workspace, the app and the referee, so check it with
  `AGENT_SCOPE='*'`, not with a single boundary.
- Front matter allows `#` comments, on a line of their own or after the values. Pin the parser
  with a referee test of its own: every other check reads through it.
- The referee's agent file lists every referee test, and a referee test checks that, so a new
  test cannot land without saying what its failure means.
- Never quote an injection phrase in an agent file, not even in a security note: Hermes's
  scanner then drops the whole file (`agent-context-files`).
