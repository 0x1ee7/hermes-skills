# Project Context Files

Hermes injects project-level instructions into the system prompt by reading context files from the working directory. The discovery order is **first match wins** — only one project context source is loaded per session.

| File (in priority order) | Discovery | Use when |
|---|---|---|
| `.hermes.md` / `HERMES.md` | Walks parents up to the git root, stops at git root | You want hierarchical project rules (root + per-package overrides) |
| `AGENTS.override.md` / `AGENTS.md` / `agents.md` | **Chain from the git root down to the cwd**, merged: one file per directory (the override wins in its directory), identical copies deduplicated. Cwd only outside a git repo | You want portable agent instructions that work the same in Hermes, Claude Code, Codex, etc. |
| `CLAUDE.md` / `claude.md` | Cwd only | Same as AGENTS.md, Claude-flavored |
| `.cursorrules` / `.cursor/rules/*.mdc` | Cwd only | Migrating from Cursor |

`SOUL.md` (in `$HERMES_HOME`) is independent and always loaded when present — it sets the agent's identity, not project rules.

### Pick the right one

- **Use `.hermes.md`** when you want Hermes-specific behavior that lives above the cwd (root + subtree), or when you want rules to inherit from a parent directory. The parent walk stops at the git root, so a home-level `.hermes.md` won't leak into every project (a git repo's root is the boundary).
- **Use `AGENTS.md`** when the same project will also be worked on by other agents (Codex, Claude Code, OpenCode). Hermes, like Codex, merges the `AGENTS.md` files from the repo root down to the cwd, so a per-folder file (one per crate or package) adds to the root one when a session starts in that folder.
- **An `AGENTS.md` shadows `CLAUDE.md`.** Only one type loads, so once any `AGENTS.md` is on the chain Hermes never reads `CLAUDE.md`: adding an `AGENTS.md` to a repo whose rules live in `CLAUDE.md` silently drops those rules from Hermes sessions. Keep one canonical text in `AGENTS.md` and make each `CLAUDE.md` just the Claude Code import line `@AGENTS.md`.
- **Don't put project rules in `~/.hermes/AGENTS.md`** (or any other home-level location). When Hermes runs with that directory as cwd, the file loads — but only for that one directory. For cross-project context, use `SOUL.md` (in `$HERMES_HOME`, identity-only) or install a skill via `hermes skills install`.

### Size and truncation

Each context file, and the merged `AGENTS.md` chain as a whole, is capped at max(20,000 characters, 6% of the model's context window in characters). Text past the cap gets **head + tail** truncated (the middle is dropped, with a `[...truncated...]` marker). Budget for the worst case: root file plus the largest per-folder file under 20,000 characters. For large project rules, prefer splitting into multiple skills over cramming one file.

### Check what a session will load

Run Hermes's own loader (source: `agent/prompt_builder.py`, `build_context_files_prompt`) for any folder; it prints exactly the project context a session started there gets. Use the interpreter from `hermes --print-runtime-command` and import `hermes_bootstrap` first, or third-party imports fail:

```bash
PY="<python.exe from: hermes --print-runtime-command>"
"$PY" -I -c "import sys; sys.path.insert(0, r'<HERMES_HOME>/hermes-agent'); import hermes_bootstrap; from agent.prompt_builder import build_context_files_prompt as b; out = b(cwd=r'<project>/<folder>', skip_soul=True); print(len(out), '[BLOCKED' in out); print(out[:400])"
```

`_scan_context_content(text, name)` from the same module shows what the injection scanner would replace, so new context files can be checked before they are written.

### Security

All context files pass through the threat-pattern scanner (`_scan_context_content` in `agent/prompt_builder.py`) before reaching the system prompt. For project files (`AGENTS.md`, `.hermes.md`, `CLAUDE.md`, `.cursorrules`), one match replaces the **whole file** with a single `[BLOCKED: <file> contained potential prompt injection (...). Content not loaded.]` line, so a security note that quotes a phrase like "ignore previous instructions" drops every rule in that file. Describe such attacks without quoting them, and scan drafts first (the `agent-context-files` skill has a script). Only a user-authored `SOUL.md` in `HERMES_HOME` gets a logged warning instead.

### Disable for one session

`hermes --ignore-rules` skips auto-injection of all project context files (`.hermes.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`) **and** `SOUL.md` identity, plus user config, plugins, and MCP servers. Use it to isolate whether a problem is your setup or Hermes itself.

### Example: a small `.hermes.md`

```markdown
# My Project

Hermes: when working in this repo, follow these rules.

## Build
- Always run `make test` before declaring a change done.
- Use `uv run` for Python, not `pip install`.

## Style
- Prefer `pathlib.Path` over `os.path`.
- No `print()` in production code — use the `logger`.
```

That file at `/home/me/projects/myrepo/.hermes.md` is auto-loaded when Hermes runs in any subdirectory of `/home/me/projects/myrepo`, but not when it runs in `/home/me/other-project`.
