---
name: omp-edit-tool-habits
description: "Use when editing files with the hashline edit tool; avoids stale anchors and range mistakes."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [tooling, omp, editing, hashline, workflow]
    related_skills: [engine-feature-delivery-loop]
---

# Habits for the hashline `edit` tool

Mistakes made (and fixed) in a 40-file session; each cost a turn.

## Rules that prevent them

1. **Anchor only on lines you have seen under the current tag.** The tool rejects an op whose lines were never displayed ("showed a partial range"). Read the exact range (`read path:A-B`) first, then edit. A straight retry with the same header succeeds after a rejection; do not re-guess.
2. **Numbers are original numbers**, not shifted by earlier ops in the same call. Within one call list ops in any order, but never touch the same line twice.
3. **`PUT N.=M:` replaces N..M inclusive; the body is the complete final content.** Do not repeat the unchanged row after the range (the tool "repairs" some echoes; do not rely on it). Check what the line *is* before you replace it: replacing a closing `}` or doc comment by accident compiled to a syntax error or a duplicate constant twice.
4. **Insert** with `PUT >N:` / `PUT <N:` (needs `+` body rows). **Delete** with `CUT N.=M` (an empty `PUT` is read as a delete but warns).
5. After any edit, the response gives a **new tag**; use it, or re-read. A stale tag is sometimes recovered with a warning: treat that as a reason to look at the diff region.
6. Whole new file: `write`. A file you wrote yourself and now restructure heavily: rewrite it with `write` rather than patching blind.
7. Never edit with `sed`/`python` through bash for single edits (the harness forbids it); shell tools are for formatting (`cargo fmt`), counting and builds.
8. After a multi-op edit run the compiler immediately; the tool also warns "no longer parses" for supported languages: fix it before anything else.
9. Imports: add them with a separate `PUT <N` on a displayed line near the top; ranges at line 1-12 are usually not displayed until you read them.

## Habit

`read` range -> one edit call with all related ops -> check the echoed region -> `cargo fmt && cargo check`. For line-count tables in docs (reading order), take counts from `wc -l` after the final edit.

## Shell quirks on the Windows host (Git Bash under the tool)

- **Never `cd C:/...` in a command.** It fails ("volume label syntax is incorrect") and short-circuits
  an `&&` chain: it silently skipped a release build (the copy was a stale binary), a file restore and
  a docs edit in one week. Set the tool's `cwd` instead; after a chain, check its first real output.
- **No `/dev/null` and no process substitution** (`2>/dev/null`, `<(...)`): write to a temp file.
- **`env VAR=x cmd` fails**; write `VAR=x cmd`.
- **`.git/index.lock` exists**: another git process holds it. Check `tasklist | grep -i git` and wait a
  few seconds; it clears itself. Never delete it while a git process may be running.
- **A `git checkout -b` that failed** leaves you on the old branch: confirm with
  `git branch --show-current` before the first commit.
