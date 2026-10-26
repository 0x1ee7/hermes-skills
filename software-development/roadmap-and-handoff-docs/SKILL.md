---
name: roadmap-and-handoff-docs
description: "Use to keep a roadmap, queue and handoff docs that agents can resume from."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [roadmap, handoff, queue, planning, agents-md, documentation]
    related_skills: [agents-md-boundary-system, parallel-agent-task-protocol]
---

# Roadmap, queue and handoff docs

Agent files stay static; changing state lives in three documents so that tasks do not become
agent-file edits.

## When to Use
- Starting or closing a batch of work in a repo with boundaries.
- Writing "where we are" for the next agent or session.

## Documents
- **`docs/roadmap.md`**: the one list of what is open. A table per theme with columns
  `ID | What | Scope | Notes`. Scope is a boundary name, so items in different scopes can be
  run side by side. Also: "Suggested order", "Gated" rows (start only when a stated condition
  holds, such as a measured cost), "Not yet verified" (heard, run or seen by nobody), and
  "Declined" (do not reopen without the user). Finished rows are removed and summarised in a
  "Done, by theme" table with pointers to the agent files that now describe them.
- **Queue files** (`docs/<name>-queue.md`): a checklist plus work log for one batch, citing
  commit hashes. Pending agent-file changes go in an "Agent files" section; the root file says
  such a list is newer than the files. When applied, write "Applied on <date>; nothing pending"
  at its top. Finished queues move to `docs/history/`.
- **`docs/handoff.md`**: state of `main` (pushed or not, last green commit, tags), what just
  landed, and the next steps. Read first by the next agent.
- **Plans** (`.hermes/plans/`): the design behind a queue; scratch for agents, never a leak.

## Rules
- IDs are stable and prefixed by theme (`L-` limits, `S-` shooter, `C-` content).
- New findings from a session become new rows with a one-line repro hint (for example S-5: log
  the impact point of a third-person shot), not silent TODOs.
- Numbers (tests, lines, timings) come from commands run now.
- Keep the root file's pointer to these documents static; never put item IDs or progress in an
  `AGENTS.md`.
- Regenerate generated docs (asset lists, maps) in a final commit and verify with their
  `--check` flags.
