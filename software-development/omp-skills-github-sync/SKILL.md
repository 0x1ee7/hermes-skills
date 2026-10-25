---
name: omp-skills-github-sync
description: "Use when omp skills change; compare them with the repo and push to GitHub."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [skills, backup, sync, git, github, omp]
    related_skills: [local-skills-github-sync]
---

# omp skills -> GitHub sync

Compares the skills omp loads with the skills repo and pushes what changed.

Defaults on this machine: repo `D:/dev/hermes-skills` (remote `origin` = github.com/0x1ee7/hermes-skills), branch `main`. omp loads the repo's `software-development`, `media` and `creative` folders in place through `skills.customDirectories`, so editing one of those skills edits the repo. Override the repo with `--repo` or `OMP_SKILLS_REPO`.

## When to Use

- Right after creating, editing or deleting an omp skill.
- The user asks to compare, back up, sync or push their omp skills.

## Run

    python skill://omp-skills-github-sync/scripts/sync_omp_skills.py --dry-run
    python skill://omp-skills-github-sync/scripts/sync_omp_skills.py

Stdlib only (Python 3.8+); needs `omp` and `git` on PATH. Flags: `--dry-run` (compare only), `--no-push`, `--repo`, `--branch`, `--remote`.
Last line: `RESULT: up-to-date | dry-run: ... | committed <sha> (not pushed) | pushed <sha> ... | blocked: <reason>`. Exit 0 ok, 1 setup, 2 repo state, 3 secret/large file, 4 push.

## What the script does

1. Checks the branch, fetches, fast-forwards; stops if the branch diverged from the remote.
2. Reads `omp skill list --json`. Skills inside the repo are used in place. User-level skills outside it (`~/.omp/agent/skills`, autolearn `managed-skills`, custom dirs elsewhere) are copied to `<repo>/omp/<folder>/`, which is rebuilt from them on every run. Project, registry, plugin and other tools' skills are skipped.
3. Compares the working tree with HEAD per skill folder (`<category>/<skill>`) and prints new / updated / removed.
4. Blocks token/private-key patterns and files over 50 MB.
5. Commits all changes (`feat(skills): add x`, `chore(skills): update y; remove z`), pushes, and checks that the remote branch equals local HEAD.

## Workflow

1. Run with `--dry-run`; show the comparison.
2. Run for real; report the RESULT line.

## Rules

- Never bypass a secret block: report the file:line and let the user fix the skill.
- Diverged branch or failed fast-forward: stop and show the output; never stash, reset, or force-push.
- `<repo>/omp/` is generated: edit the source skill, not the copy. Never add `<repo>/omp` to `skills.customDirectories` (the script stops).

## Pitfalls

- Drive D: does not record file ownership; the script passes `-c safe.directory=<repo>` to every git call.
