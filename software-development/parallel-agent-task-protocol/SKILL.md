---
name: parallel-agent-task-protocol
description: "Use to run several coding agents in git worktrees and merge their branches safely."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [parallel-agents, git-worktree, merge, handoff, integrator, subagents]
    related_skills: [agents-md-boundary-system, agent-referee-checks, roadmap-and-handoff-docs, rust-game-backlog-execution]
---

# Parallel agent task protocol

How to run N agents at once on a repo that has boundaries (`agents-md-boundary-system`) and how
the integrator lands their work. Learned on a 8-branch, 2-wave run.

## When to Use
- A backlog has items in different scopes and the user wants them done in parallel or "fully
  automated".
- Not for one item, or two items in the same boundary (they cannot run side by side).

## Procedure
1. **Slice by scope.** From the roadmap table (scope column), pick items whose boundaries do not
   overlap and none of which changes a contract another uses. Put dependent items in wave 2
   (for example an engine half, then the game half that uses it).
2. **Isolate each task**: `git worktree add ../<repo>-<task> -b agent/<task> <base>` and its own
   build-output directory (`CARGO_TARGET_DIR`, `node_modules` cache, etc.) or builds queue on one
   lock. On Windows put output on NTFS if the repo drive cannot hard-link.
3. **Brief each agent in full** (they lack the conversation): the goal, `AGENT_SCOPE`,
   `AGENT_BASE`, the contract to honour, acceptance, the gate commands, and these rules:
   - **Use absolute worktree paths for every edit.** Relative paths leaked edits into the main
     checkout in practice; after each wave run `git status` in main and move strays.
   - Do not touch workspace files (manifests, lockfile, CI, root docs): file an interface request.
   - Keep your own `AGENTS.md` true in the same change; do not edit the referee.
   - Skip build/lint mid-flight if tasks are many; run the gates once at the end.
   - Finish with the hand-off note below.
4. **Hand-off note** (every agent): `Task, Scope, Base, Branch; Changed; Contract (none | added |
   interface request); Tests (which failed before); Verified (commands, green); Not verified
   (why); For the integrator`.
5. **Integrate one branch at a time**: merge, resolve conflicts (usually the AGENTS.md Tests and
   Reading-order lines and one hot source file; keep both intents), run formatter and check
   `git status` (it reformats stray files), then the gates with `AGENT_SCOPE='*'`.
6. **Apply interface requests** as the integrator's own commit, then start wave 2 from the new
   main.
7. **Close**: update roadmap rows (`roadmap-and-handoff-docs`), regenerate generated lists in a
   last commit that changes nothing else, remove worktrees and branches
   (`git worktree remove --force`, `git branch -D`), run every gate, run the referee on a second
   OS if available, and push only when the user says so.

## Rules
- Commits are modular with a why-body; no co-author trailers unless asked.
- If an agent dies mid-run (API error), restart it in the same worktree; its commits remain.
- A leaked scope check inherited from a merge is fixed on the owning side, not by reverting.
- Windows host: LF line endings, `C:/` style paths, give each agent its own target directory.
- Verify headless smoke and the real surface (screenshots for UI); an agent's "tests pass" is
  not proof that a feature works in play. Record what was not seen in the roadmap.
