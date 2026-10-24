---
name: agent-context-files
description: "Use when writing AGENTS.md or CLAUDE.md for agent tools."
version: 1.1.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [agents-md, claude-md, context-files, hermes, claude-code, codex, project-rules]
    related_skills: [hermes-agent, parallel-agent-boundaries]
---

# Agent context files

Agent tools read a repository's instruction files differently, and a file one tool reads can
silently stop another from reading its own. This skill keeps one canonical text, `AGENTS.md`,
that every tool loads, makes each `CLAUDE.md` import it, and checks what a session started in
any folder actually receives, with Hermes's own loader and injection scanner.

## When to Use
- Writing, moving or splitting `AGENTS.md`, `CLAUDE.md` or `.hermes.md`, at the root or per
  folder.
- A repo keeps its rules in `CLAUDE.md` and someone adds an `AGENTS.md`, or the reverse.
- An agent ignores the project's rules in some folder, or its context looks cut short.
- Not for what the rules say (the project decides that), and not for splitting a repo into
  scopes for parallel agents (`parallel-agent-boundaries`, which uses this skill).

## Support files
- `scripts/check_context_files.py`: `load <folder>... [--expect TEXT]` prints which files a
  Hermes session started in each folder loads, shadows or skips, the size, and whether anything
  is truncated, blocked or missing; `scan <file>...` shows what the injection scanner would
  replace in drafts before they are written. Runs under any Python: it re-launches itself in
  Hermes's interpreter via `hermes --print-runtime-command`.

## How the tools load them
- **Hermes** (`agent/prompt_builder.py`, `build_context_files_prompt`): exactly one kind of
  project file loads, the first kind found of:
  1. `.hermes.md` / `HERMES.md`, the nearest, walking up to the git root;
  2. the `AGENTS.md` chain: in each directory from the git root down to the cwd, the first of
     `AGENTS.override.md`, `AGENTS.md`, `agents.md`, all merged, identical copies dropped;
  3. `CLAUDE.md` in the cwd only;
  4. `.cursorrules` and `.cursor/rules/*.mdc` in the cwd only.

  So one `AGENTS.md` anywhere on the chain shadows every `CLAUDE.md`. Each file, and the merged
  chain, is capped at `context_file_max_chars` from config.yaml when set (it wins on every
  path), else at max(20,000 characters, 6% of the model's window in characters): 240,000 for a
  1M-token window, but always 20,000 for `delegate_task` subagents, whose prompt builder passes
  no window. Subdirectory hints have their own fixed 32,000 cap. Beyond the cap the middle is
  cut. If the injection scanner matches anything in a project file, the
  whole file is replaced by one `[BLOCKED: ...] Content not loaded.` line. Front matter is
  stripped from `.hermes.md` only, so an `AGENTS.md` front matter reaches the model as text.
  During a session, when a tool call touches files in a sub-folder that has its own
  `AGENTS.md`, Hermes appends that file to the tool result ("Subdirectory context
  discovered"), so per-folder guides reach an agent started at the root as soon as it works
  there.
- **Claude Code** reads `CLAUDE.md`: the project's at start-up, a sub-folder's when it reads
  files there. It follows `@path` imports (relative to the importing file, not inside code
  spans or blocks), and does not read `AGENTS.md` by itself.
- **Codex** and most other tools read `AGENTS.md`. Check each tool's docs for its discovery
  rules before relying on per-folder files.

## Procedure
1. Inventory: `git ls-files '*AGENTS.md' '*CLAUDE.md' '*.hermes.md' '*.cursorrules'`, and
   which tools the team runs. Done when you know where every rule lives today.
2. Make `AGENTS.md` canonical. Move the text of each `CLAUDE.md` into the `AGENTS.md` beside it
   word for word (`## Commands`, `## Rules` and so on first, new sections after), then turn every
   `CLAUDE.md`, the root one included, into this shim:
   ```
   Claude Code reads this file; the guide that every agent shares is [AGENTS.md](AGENTS.md),
   imported here:

   @AGENTS.md
   ```
   Use visible text, not an HTML comment, so a person who opens the file sees where the rules
   went.
3. Per-folder guides: an `AGENTS.md` and a shim in each folder an agent may be started in or
   work in. Keep the root file plus the largest folder file under the cap that applies to
   every path: `hermes config get context_file_max_chars` (this user: 40,000), else 20,000.
4. Draft each file as `*.draft.md` (in `.hermes/` or scratch), then run
   `check_context_files.py scan` over the drafts. Hermes guards writes to `AGENTS.md`,
   `CLAUDE.md`, `.cursorrules`, `SOUL.md` and the project's `.hermes/` tree: a write may wait
   for the user's approval, and an unanswered prompt times out. Write everything in one batch
   while the user is there.
5. Verify after writing:
   - each written file equals its draft (`cmp`);
   - every line of each old `CLAUDE.md` is in the new `AGENTS.md`
     (`git show HEAD:CLAUDE.md | while IFS= read -r l; do [ -z "$l" ] || grep -qxF -- "$l"
     AGENTS.md || echo "$l"; done`), apart from lines reworded on purpose;
   - `check_context_files.py load <root> <each folder with a guide> --expect '## Rules'`: the
     right files load, nothing is shadowed by mistake, truncated or blocked;
   - every repo `--check` gate: tools that list a folder may now count the guides as files.
6. Point docs that call `CLAUDE.md` the home of the rules (README, comments in manifests, test
   docs) at `AGENTS.md`. Leave historical logs alone.

## Rules
- Never add an `AGENTS.md` to a repo whose rules live in `CLAUDE.md` without moving them: Hermes
  would stop loading `CLAUDE.md`, and nothing warns about it.
- Check what loads with Hermes's code, not with its docs: the docs once said `AGENTS.md` was read
  from the cwd only, while the code merges the chain from the git root.
- If `write_file` keeps refusing to overwrite an existing `CLAUDE.md` as "not fully read" even
  after a full read, replace its whole text with `patch`.
- Never quote an injection phrase ("ignore previous instructions" and the like) in a guide, not
  even in a security note: one scanner match drops the whole file, every rule with it. Describe
  the attack instead, and scan drafts before writing them.
- A guide's front matter costs context in every session: keep it to what tests or tools read.
- Keep agent files free of work in progress: no item IDs, progress or plan details. They go
  stale and turn every task into an agent-file edit, which needs an approval. The root file
  carries one static pointer to where work is tracked (queue files, plans) and says that a
  queue's pending agent-file changes are newer than the files. While edits cannot be approved,
  freeze the files and collect each pending change in the queue, by file, for one batch later.
- Applying such a batch: fold each file's entries in order (the later wins; superseded features
  drop out), drop the item IDs, and measure every count and line number against today's code,
  not the entries. Then put "Applied on <date>; nothing here is pending" at the top of the
  queue section and update the handoff's and the plan's next steps. Under the "queue is newer"
  rule, a list without that line gets applied again, stale entries included.
- Size each draft together with the root file before writing (`check_context_files.py load`
  after, `--expect` per folder). The boundary that collected the most entries outgrows the
  cap first: shorten by pointing at the docs (a design doc, the other boundary's Provides)
  rather than dropping invariants.
