---
name: local-skills-github-sync
description: "Use when local Hermes skills change; push them to GitHub."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [skills, backup, sync, git, github]
    related_skills: [github, hermes-agent]
---

# Local skills -> GitHub sync

Mirrors the user's own (local) Hermes skills into a git repo and pushes when anything changed. Builtin and hub skills are never copied.

Defaults on this machine: repo `D:/dev/hermes-skills` (remote `origin` = github.com/0x1ee7/hermes-skills, private), branch `main`. Override with `--repo` or `HERMES_SKILLS_REPO`. Branch `all-skills` is a frozen snapshot of every skill; the script never touches it.

## When to Use

- Right after creating or patching a local skill (skill_manage create/patch/write_file on a skill whose source is local).
- The user asks to back up, sync, or push their skills.
- Not for edits to builtin/hub skills: they are not local and are not synced.

## Run

    python "$HERMES_HOME/skills/software-development/local-skills-github-sync/scripts/sync_local_skills.py" --dry-run
    python "$HERMES_HOME/skills/software-development/local-skills-github-sync/scripts/sync_local_skills.py"

Stdlib only (Python 3.8+). Flags: `--prune` (delete repo skills that are no longer local), `--no-push`, `--branch`, `--remote`, `--skills-dir`, `--classify auto|cli|fs`.
Last line: `RESULT: up-to-date | dry-run: ... | pushed <sha> ... | committed ... | blocked: <reason>`. Exit 0 ok, 1 setup, 2 repo state, 3 secret/large file, 4 push.

## What the script does

1. Refuses a dirty repo or wrong branch; fetches and fast-forwards; stops if diverged.
2. Local set = rows of `hermes skills list --source local` (run with COLUMNS=400 so names are not truncated). If the CLI is missing or unparseable it falls back to the on-disk rule Hermes uses (not in `skills/.bundled_manifest`, not in `skills/.hub/lock.json`) and says so; it warns when the two disagree.
3. Mirrors each local skill to the same `<category>/<name>/` path in the repo (skips `__pycache__`, `*.pyc`, `node_modules`, `.venv`).
4. Before copying anything, blocks token/private-key patterns and files over 50 MB.
5. Commits with a conventional message naming the skills (`feat(skills): add x`, `chore(skills): update y`), pushes, and verifies the remote branch equals local HEAD.

## Workflow

1. Run with `--dry-run`; show the plan (new / updated / stale).
2. Run for real; report the RESULT line to the user.
3. Stale skills (deleted or moved locally) stay in the repo. Prune only when the user agrees, with `--prune`.

## Rules

- Never bypass a secret block: report the file:line and let the user fix the skill.
- Dirty repo or diverged branch: stop and show the output; never stash, reset, or force-push.
- Pushing to the user's backup repo after a local skill change is in scope; ask before pruning.

## Pitfalls

- Auth: the repo pushes over HTTPS with a repo-local `gh auth git-credential` helper; SSH works too. A failing bare `ssh -T git@github.com` in Git-bash proves nothing; test with `git ls-remote` (see the auth notes in the github skill).
- Drive D: does not record file ownership; the script passes `-c safe.directory=<repo>` to every git call.
- Skills under `skills.create_dir` or external dirs are reported as "not under skills dir" and skipped.
