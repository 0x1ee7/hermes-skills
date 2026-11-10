---
name: subagent-path-and-broadcast-hygiene
description: "Use when fanning out many subagents, especially outside the session repo; not for single-agent edits."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [parallel-agents, subagents, orchestration, omp, paths, verification]
    related_skills: [parallel-agent-task-protocol, parallel-agent-boundaries, tdd-exercise-repo-harness]
---

# Subagent path and broadcast hygiene

Lessons from a 59-agent run writing into three repos that were not the session's working
directory. `parallel-agent-task-protocol` covers worktrees and merging; this covers the
orchestration traps.

## When to Use
- More than a handful of `task` agents at once, or agents working outside the session cwd.

## Rules
1. **Every agent's tools start in the session cwd.** Relative paths (`exercises/x/y.go`) land in
   the session repo, not the target one; agents then report their files "vanished" and may
   suspect peers. Put in the shared context: absolute paths for every read/write/edit, `cwd` on
   every bash call. Run `git status` in the session repo during and after the run; move strays.
2. **Unexpected modifications there may be the user's own work** (they keep working between
   sessions). Never revert a file you did not write; name it to agents as off-limits.
3. **Over-capacity tasks queue** (about 32 run at once). Messages to a queued agent fail with
   "not running"; a broadcast reaches only running ones. Re-send setup warnings to each agent as
   it starts (poll in a loop in one long `eval` cell; a background asyncio task in the kernel
   does not progress between cells).
4. **Broadcasts wake idle agents and can derail running ones.** A broadcast caused one agent to
   answer the message and report "completed" with zero files written; another stopped to ask a
   question. After any broadcast, read each completion for evidence (file list, both test counts)
   and re-task with a full self-contained instruction when it is missing.
5. **Shared harness bugs found mid-run**: fix centrally, then message only the affected language's
   agents with what changed and what to redo (reconfigure, rebuild solutions dir).
6. **Shared files need one owner.** Pre-add dependencies before spawning (go.mod, Cargo
   workspace deps, gtest source) and forbid agents from editing manifests; glob-based workspace
   members break every build while one agent's crate is half-written, so tell agents to write the
   manifest first.
7. **Per-agent build dirs** (`build/<NN>`, `-DONLY=<topic>`) or a warm shared target with lock
   waits explained in the brief.
8. **Trust no report until re-run.** At least one agent reported counts it never ran. Re-run
   every verification centrally in one pass per repo before committing.

## Verification
- Session repo `git status` shows only the user's own changes.
- Every topic directory exists in the right repo and the central re-run matches each report.
