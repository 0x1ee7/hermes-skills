---
name: rust-game-backlog-execution
description: "Use when implementing a Rust engine backlog item by item."
version: 1.3.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [rust, cargo, wgpu, winit, bevy_ecs, tdd, git, windows, verification]
    related_skills: [rust-workspace-review, test-driven-development, requesting-code-review, parallel-agent-boundaries]
---

# Executing a Rust game-engine backlog (one verified commit per item)

Companion to `rust-workspace-review`, which writes `docs/upgrade-backlog.md`. This skill is the
implementation loop, ways to verify engine changes without a GPU or without touching the user's
desktop, and the pitfalls that cost time.

## When to Use
- The user asks to implement items from a review/handoff backlog in a Rust (wgpu/winit/bevy_ecs)
  workspace, usually with "a commit per item".
- Skip for the audit itself (use `rust-workspace-review`) or a single quick fix.

## Support files
- `scripts/gates.sh`: fmt, clippy, tests, optional `smoke` and `doc`; one summary line per gate,
  exit 1 at the first red one. Smoke command and log patterns come from `SMOKE_*` env vars.
- `scripts/mutate.py`: mutation checks from a JSON list (path, exact old text, new text, test
  that must fail); restores byte for byte, then runs the crate's suite.
- `scripts/lint-sites.sh`: every site of one warning as `path:line|source line`.
- `scripts/ab.sh`: times a before and an after binary, alternating runs, and prints the means.
- `references/engine-recipes.md`: GPU-free test recipes; API notes for wgpu 30, winit 0.30,
  bevy_ecs 0.20 and gltf; fixed-timestep, texture and skinned-import recipes; rules for
  see-through and cutaway features (what may fade, the see-through circle).
- `references/windows-harnesses.md`: window capture, pixel diff, CPU-while-minimized scripts.
- `scripts/capture-keys.ps1`: start the game, play keys into its own window, capture at named
  steps; the same step string replays into a before and an after build.
- `scripts/capture-window.py`: puts the iso-engine player on a tile (a scratch copy of the
  assets with the map's spawn moved, loaded through `ISO_ASSET_ROOT`) and captures the window.
- Everything else done to a game window (keys, wheel, captures, diffs, tiled crops, closing):
  the skill `game-window-control`.

## Setup (once per session)
1. Choose an absolute scratch dir. Copy the scripts there from the skill directory (`skill_view`
   reports it), add wrappers such as `g` = `git -c safe.directory=<repo> "$@"` if git reports
   dubious ownership, then `export PATH="$SCRATCH:$PATH" LOGS="$SCRATCH"`. Shell functions never
   persist between terminal calls, and exported variables can be lost too (see Pitfalls).
2. Make the plan current, and track it. When the backlog follows a plan written before recent
   commits, check its assumptions against the repo (moved modules, renamed docs, new callers
   such as an integration suite) and fix them in the plan, under a short "Changes since this
   plan was written" section. This user wants the plan committed (`.hermes/plans/`, in the
   queue's first commit) with a Progress section that every commit of the queue updates: what
   the commit finished, what comes next, what waits for a decision or an approval.
3. Get every approval the run will need while the user is there: window captures (PowerShell
   with `-ExecutionPolicy Bypass`), writes to `AGENTS.md`, deletions. A prompt that comes while
   they are away times out, and a timed-out action must not be retried or done another way.
4. Run `gates.sh smoke doc` and record the test count as the baseline.

## Loop per item
1. Re-read the item and every file it cites. Check crate APIs in the local source
   (`~/.cargo/registry/src/*/<crate>-<ver>/`), not from memory. Grep the whole workspace,
   integration tests included, for every public signature the item changes: a plan written
   before a caller existed does not list it, and the caller changes in the same commit.
2. Test first, by kind of change:
   - New or changed behaviour: write the test, run it, see it fail for the stated reason. A test
     that passes against the old code tests the wrong thing (an f32-vs-f32 comparison rounds
     both sides the same way; compare the increment instead).
   - Existing behaviour (tests for untested code, a safety net before a refactor): it passes at
     once by design, so mutation-check it. `cp f $SCRATCH/f.bak`, break the code with `sed -i`
     (reverse a sort, swap two corners; escape `&` in the replacement), see the test fail, copy
     the backup back, see it pass. Restore from the copy: `git checkout` would also discard the
     item's uncommitted work.
   - Logic behind GPU calls: first move the CPU part verbatim into free functions over plain
     data, with GPU state passed in as a predicate, then test those. For shaders see
     `references/engine-recipes.md`.
3. Implement in an order where every intermediate state passes the gates: fix the call sites
   before switching anything on (lint level, cull mode, feature flag), so an interrupted
   session leaves a green tree.
4. `gates.sh smoke`, adding `doc` when docs or public APIs changed. Put the project's fallback
   warnings (placeholder model, ambiguity warnings) into `SMOKE_BAD` so they fail the smoke run.
5. Tick `- [x] <ID>` and append a work-log line: files, tests added, what was measured, and what
   was NOT checked and why (no HiDPI display, an error path that never fired).
6. Commit the item as a series of modular commits, one logical change each, so every commit is
   easy to review, bisect and revert: a refactor apart from the feature that needs it; engine
   code apart from game code; a tool change apart from the content it later produces; generated
   assets together with the generator change and manifest keys that produced them; content
   placement (maps, levels) apart from the assets; docs with the change they describe. Every
   commit must build and pass the gates on its own (the next commit must not be needed to make it
   compile, e.g. no item unused until a later commit, which `-D warnings` rejects as dead code).
   The item's last commit ticks it and adds the work-log line. Chain each one so a red gate never
   commits: `gates.sh smoke && g add <files> && g commit -q -F - <<'EOF'`. Message: imperative
   subject, a short why-body and `Backlog: <ID>.` (or the queue's trailer); `git log --grep
   '<ID>'` then lists an item's commits. No `Co-Authored-By` trailer for the agent: this user
   dropped it, and copying trailers from recent commits would bring it back. When a repo's
   commit rules say otherwise, change the rule in the repo rather than following it.
   Docs that cite commits by hash (a work-log line listing the item's commits, a generated asset
   list) are updated by the item's closing commit, which comes last and changes nothing they
   list: a commit cannot name its own hash. Every commit also updates the plan's Progress
   section (Setup step 2).
   While the user is reviewing on screen (sending screenshots, wanting to run the game), leave
   visual changes uncommitted until they approve: say where to look (level, spot, keys) and how
   to undo (`git restore <files>`). Commands for them to run: try them first in the same shell,
   give the Git Bash and the PowerShell form, and end with the restore step.
7. Items needing a user decision (licence holder, design option, new dependency, CI cost): skip
   and list them at the end. Never invent the answer.
8. Bug reports: before removing code, confirm the suspected cause in the red test by switching
   only that cause off (a setting, a temporary edit restored from a copy): the test must turn
   green. When the report is a screenshot of a real level, also sweep the real geometry: append
   a throwaway test to an existing integration test file (from a backup copy), load the level,
   move the player along the spot, print the old and the new decision per position
   (`--nocapture`), then restore the copy. It shows the bug zone, and whether the user's
   explanation is the cause ("two things in between" was really one long thing).
   Flicker reports: diff the user's screenshots pairwise (identical first and last frames mean
   two alternating states), mask where they differ, then reproduce with captures that change
   nothing between them (skill `game-window-control`); when the still scene is stable, repeat
   the user's last actions (walk into a wall, stop) before capturing. Count distinct per-frame
   values (drawn positions, the camera eye) in a throwaway probe to find what moves at rest. Then the fix removes the real cause, and the work log can say it was the only one.
   The same switch answers "is X still needed?": disable X with a one-line edit, run the suite,
   report the failing tests by name (they are what X provides), then restore.

## Finish
Report one line per commit (sha, ID, change), a "not verified" list, any uncommitted state with
the exact command to undo it, and the open decisions as direct questions.

Ending a session ("finalize, new work starts from a new context"):
- Write the handoff into the repo, not only the chat: a short `docs/handoff.md` with the state
  of every queue (a table), the next steps in order with the decisions they wait on as
  questions, what was never seen on screen, the known limits with a pointer to where each is
  written down, and how work is done here (rules, gates, the skills that carry the workflow).
  No machine-local paths. Point the finished queue and the plan's `Next:` at it, and commit it
  last, apart from the item's closing commit.
- Push only when asked; `git fetch` first and check `git rev-list --left-right --count
  origin/main...main` (behind must be 0; never force). Push existing tags only by name.
- Watch the CI run of the push (`gh run list --branch main --limit 1`, then `gh run watch <id>
  --exit-status` in the background) and report its result: it is the only check of the
  software-rendered path. When git needs a `safe.directory` wrapper (exFAT), `gh` run inside
  the repo fails with "dubious ownership": pass `--repo <owner>/<name>` instead.

Tagging a milestone when asked: match the existing tags (`git for-each-ref refs/tags
--format='%(refname:short) %(objecttype)'`), prefer an annotated tag whose message lists what the
milestone holds, put it on the closing commit, and give the push commands (branch, then tag)
instead of pushing.

## Splitting commits that came out too big (unpushed only)
When an item already landed as one large commit, rebuild it as modular commits on a new branch
from its parent, keeping the old series on a backup branch:
- For each new commit, list which files come verbatim from which old commit
  (`git checkout <old> -- <paths>`) and which need an intermediate version no commit has. Build
  those with a script of exact, asserted string edits on the old versions, so a wrong assumption
  fails loudly; regenerate intermediate generated files by replaying the deterministic scripts
  and prove it by replaying the next step and comparing with the old commit byte for byte.
- Drive the replay with a script: clean tree, place files, `cargo fmt`, all gates, rebuild
  generated assets and compare hashes, commit; stop at the first failure.
- Pass Windows-form paths (`C:/...`) to native tools like git (`commit -F`).
- Finish with `git diff <old-tip> <new-tip>` empty, then move the branch
  (`git switch main && git reset --hard <new-tip>`); tell the user the backup branch name.

## Pulling upstream into a queue branch
When the user asks for main's updates while a queue branch is unmerged: `git fetch`, then merge
(`git merge --no-ff --no-commit main`), not rebase: the work log and the asset list cite the
branch's hashes. Resolve generated files by regenerating them (maps from recipes, textures
from the generator, then pixel-compare and restore the unchanged ones), give main's glyphs,
keys and names precedence where both sides added the same thing, and refresh the asset list in
the commit after the merge. Gate the merged tree with `AGENT_SCOPE='*'` before committing it.

## Committing a finished working tree as several commits
When several logical changes already sit uncommitted in one tree:
- Order the commits so each stands alone: what others rely on first (a library split, a tool
  fix), then the change that needs it. Things that need each other (a test suite and the files
  it checks) go in one commit.
- When one file holds hunks of two commits, or an earlier commit's docs or comments would name
  something only a later commit adds, write that file's earlier version to scratch with
  asserted string edits, and stage it without touching the working tree:
  `g update-index --add --cacheinfo "100644,$(g hash-object -w <scratch file>),<path>"`.
- Gate the exact tree of every commit before making it: `g worktree add --detach <scratch>/cN
  HEAD`, put that commit's file versions in, and run every gate there. If a commit ends up
  differing from what was gated, check the commit out in a worktree, gate it, and amend before
  building on it. Then `g worktree remove --force <dir>` and `g worktree prune`.
- When every commit must also update the queue and the plan, keep their per-commit edits in one
  stage script (`stage.py <commit> <tree>`, asserted replacements) and run it in the worktree
  before gating that tree. The closing stage takes the item's commit hashes as arguments: they
  exist only once the earlier commits are made.
- Build intermediate versions backwards from the finished file (remove what later commits add)
  or forwards from HEAD, and pin the end: `same(path, finished)` at the stage where a file
  becomes final, so a typo in an intermediate edit fails there, not in review.
- Dry-run the whole series before the first commit: every stage in order in the worktree, no
  gates, then `diff -rq --exclude=.git --exclude=target` against the main tree (only the files
  the series adds on purpose may differ), then `git checkout -- . && git clean -fd` and run it
  for real. Line counts in agent files (reading order) come out right when the stage script
  recomputes them from the worktree's files instead of carrying literals.
- Finish by `git reset --mixed <tip>` in the main tree: `git status` must list only files the
  series changed on purpose (agent files applied there, queue and plan); restore exactly those
  from the tip. A closing commit with a wrong line can be fixed with `--amend` even while the
  next stage's files sit in the worktree: stage only the corrected file.
- Give every worktree a `CARGO_TARGET_DIR` of its own. Sharing the main target folder saves the
  dependency builds but corrupts it: cargo names workspace crates' artifacts by their path
  relative to the workspace root, so the worktree's build replaces the main tree's, cargo still
  counts them fresh, and test binaries keep the worktree's `env!("CARGO_MANIFEST_DIR")`. Once
  the worktree is removed, tests that read files through it fail ("reading <worktree>/...").
  If it happened: `cargo clean -p <each workspace member>` in the main tree, then gate again.
  One scratch target shared by several worktrees fails the same way, silently: worktrees
  checked out before the first build look older than its artifacts, so the second gates the
  first one's binaries against the first one's files (here: 79 demo tests reported for a tree
  holding 91). Run them one after the other with `cargo clean -p <every member>` before each
  (dependencies stay built), or give each its own target.
- A way that rewrites nothing: build every commit as an object in a scratch index
  (`GIT_INDEX_FILE=<scratch>/index git read-tree HEAD`, `git add`/`update-index`, `git
  commit-tree $(git write-tree) -p <parent> -F <msg>`), gate each in `git worktree add --detach
  <dir> <sha>`, then move the branch once (`git update-ref refs/heads/main <tip> <old>`) and
  sync the real index with `git reset -q`; the working tree keeps what was left out. Check the
  tip against the working tree with a scratch index too (`read-tree <tip>`, `update-index
  --refresh`, `git diff --stat`): a plain `git diff <tip>` shows untracked files as deleted.
- Copy files into a worktree with a fresh mtime (`cp`, Python `shutil.copy`), never
  `shutil.copy2` or `cp -p`: an older mtime than the target folder's last build makes cargo
  take the crate as built, and the gate tests the previous commit's code. The sign: a test
  count that did not grow, or a doctest failing to import an item the copied files define.
- Cargo's "hard linking files in the incremental compilation cache failed" lines on an exFAT
  target folder are not lint warnings: clippy with `-D warnings` still exits 0.
- When the repository's `.git` sits on a drive that records no ownership (exFAT), git checks
  each worktree's git directory there too, and the main repo's `safe.directory` wrapper does not
  cover it ("dubious ownership"). Call git inside a worktree as `git -c safe.directory='*'`.

## Verification techniques
Scripts: `references/windows-harnesses.md`.
- No visual change (refactors, perf work, culling, fixes that should not show): `PrintWindow`
  captures before and after, pixel-diffed; the previous item's capture is the next baseline.
  Take the before captures from the build before the change (or one where it is still inert),
  two of them when anything in the scene animates: an after capture identical to either one
  proves no change. When an A/B comes out identical (culling on/off, asset swapped), also prove
  the switch took effect: diff against a frame that must differ, or show it in numbers, such
  as the draw counts of the exit log.
- Other views or assets: temporarily change a default or a manifest entry, capture, revert, and
  check `git diff` is empty for that file. Look at captures with `vision_analyze` when the item
  changes the picture on purpose.
- Never use `Graphics.CopyFromScreen`, `SetForegroundWindow` or `mouse_event`/`SendInput`: the
  game may not be in front, so you capture, and scroll, the user's other windows.
- Checks that need input in the game window (turn the view, walk behind something, switch
  camera): post keys to the game's own handle with the skill `game-window-control` (or
  `scripts/capture-keys.ps1`). Held keys move by wall-clock time, so a walk ends roughly where
  planned: plan it from the map and speeds, then check in the capture where the player actually
  stands. The wheel works in the background and hover does not: leave cursor checks to the
  user and log them as not checked.
- Visual changes on purpose: build the commit before the change in a detached worktree with its
  own `CARGO_TARGET_DIR` on an NTFS drive (a debug build took ~2 min), play the same step
  string into both builds (`-Exe`), compare side by side with `vision_analyze`, then crop the
  spot at full resolution (scaled 2x, nearest) when the downscaled pair is ambiguous. Remove the
  worktree and its target afterwards. A view where both builds match is still worth reporting
  (here: the change is inert there).
- Reproducing a user's screenshot: put the player on the tile it shows (`capture-window.py`),
  capture before changing anything, and sweep a few neighbouring tiles and both view turns; the
  same captures after the change make the before/after row (`gamewin.py tile`, skill
  `game-window-control`). When a capture shows something
  unexplained, print what the frame holds there (a throwaway test appended to an integration
  test file from a backup copy: extract, project each draw's centre to pixels, list the ones in
  the region with their flags) instead of guessing from the picture. Never write files into the
  user's screenshot folder: they find their newest screenshots by date there.
- Sound, without ears: append a throwaway probe test (from a backup copy, restored byte for
  byte) that loads the level headless, inserts the engine's mixer output, scripts the input,
  and after every `app.update(1/60)` mixes 1/60 s into a buffer written as a stereo WAV, with a
  log line per sound as it starts (source, sound key, intended left/right gains). Then measure
  the samples (numpy via `uv run`): spectral centroid per material proves the variants differ,
  L/R RMS of isolated events against the intended gains proves the panning, peak and clipped
  counts the mix. A running player's steps overlap everything every 0.15 s and sit centred
  (the listener follows the player): isolate other sources by standing still and turning the
  view. Leave the WAVs in scratch for the user to listen to; their ears still decide.
- A user hearing "echo" or "long tails" in synthesised one-shots: measure each file first
  (length, when it falls 40 and 60 dB below its loudest, how many strikes: a 6 dB rise within
  10 ms above -24 dB). Heel-and-toe steps are two strikes, resonances cut off by the file's end
  ring on, and a step every 0.15 s piles them up; the mixer is rarely the cause (check it clears
  its buffer). Fix the generator (one strike, decays shorter than the file, refuse a sound not
  silent at its end) and pin it with a manifest-wide test, seen failing on the old files.
- CPU while minimized: `ShowWindow(h, 6)`, sample `Process.TotalProcessorTime`, restore with
  `ShowWindow(h, 9)`. Log tick counts at pause and resume to prove the simulation did not jump.
- Smoothness/interpolation: prove it numerically in an `App`-level test (the drawn position
  advances by exactly dt each frame at 144 Hz), also with the tick rate temporarily lowered.
- Executor or perf choices: temporary `#[ignore]` bench plus an env switch, both variants 3x,
  numbers in the work log, scaffolding deleted.
- Present mode / frame pacing: log frames and fps when the smoke run exits; compare runs.
- Performance items: time the build before the change against the build after it with
  `scripts/ab.sh` (the before build in a detached worktree with its own `CARGO_TARGET_DIR`):
  alternating runs, 3-4 of ~1200 frames each with vsync off, per level, compared by their
  means. Successive single runs drift by more than a 10% change, so one run per side misleads
  either way. The before/after table goes in the work log and the architecture doc's
  measurements.

## Pitfalls
- git-bash: native tools (git, cargo, python) get no MSYS path translation; pass `C:/...` paths
  or use stdin (`git commit -F - <<'EOF'`).
- Spell absolute scratch paths out in every command, background jobs above all: those never
  inherit exported variables, and a foreground shell can lose them too (after a blocked or
  timed-out call). An empty `$SCRATCH` then runs `/gates.sh` and writes logs and target dirs
  to `/`; delete anything it left there.
- A foreground timeout over 600 s becomes a background job, with the same problem.
- A background job's completion notice can arrive long after the job ran (after a compaction or
  many turns). Tell which run it was from its own output (test count, file sizes, timestamps,
  the tree it ran in) and check `git status` before acting: the failure it reports is usually
  fixed already, so re-run or revert nothing because of it.
- A change you did not make shows up in the working tree (a `Cargo.lock` bump, an edit from
  another process): don't revert it, and don't leave it unstaged while committing other work,
  since the gates run on the working tree and every commit's tree must be what was gated.
  Commit it first, as an item of its own that says where it came from, or ask. The index is no
  different: the user's editor may stage files (often while they undo an experiment by hand).
  Check `git diff --cached --stat` before committing and build each commit's index explicitly
  (`git reset -q`, then `git add <files>` or `update-index` for in-between versions), never on
  top of whatever happens to be staged.
- Docs behind an approval gate (`AGENTS.md`): when the prompt times out, don't retry it or
  write the file another way. This user freezes agent files for a run: list the exact pending
  edits in the queue's "Agent files" section (by file; the later entry wins; the root
  `AGENTS.md` points at the queue files and says the queue is newer), go on with the code, and
  apply them later in one approval round (`agent-context-files`, Rules).
  When the integration suite checks agent files (a new crate needs its own), the items that need
  them cannot pass the gates, so leave them uncommitted and make the approval round one patch:
  copy the working tree (`git ls-files --cached --others --exclude-standard`) to scratch, `git
  init` and commit it there, apply the edits with an asserted-replace script, `git add -N` the
  new files and save `git diff` beside the plan (`.hermes/plans/*.patch`; `git apply --check`
  it in the repo). Run the suite in the copy with its own `CARGO_TARGET_DIR` (a cold build, ~4
  min) and mutate the copy's new agent file once (drop a dependency) to see the check bite.
  Measure the Hermes budget there too: root plus each boundary file under the cap every path
  gets (`hermes config get context_file_max_chars`: 40,000 here; 20,000 when unset, which is
  what `delegate_task` subagents get even on a 1M-token model);
  make room by cutting restatements (a sentence repeating a rule) before others' facts.
  When applying them with the user present: draft each file in scratch and measure it first,
  then make each file one `patch` (one approval prompt per file). `write_file` on an agent file
  can keep refusing with a stale-read error even after a full `read_file`; a single large
  `patch` goes through. Before cutting detail from an agent file, grep the docs it will point at
  for every number it drops, and add the missing ones there in the same commit.
- Lint-enforcement items: list the sites with `lint-sites.sh '<warning text>' -- -W <lint>`,
  which needs no Cargo.toml change. The `[workspace.lints]` switch goes in last (loop step 3).
- Bulk `missing_docs` fixes: drive one script from the `path:line|source` list. Insert bottom-up,
  above any `#[...]` lines, and assert each line's expected text so a stale number fails loudly.
  Single-line struct variants (`Gltf { path: String }`) must be split before their fields can
  carry docs; self-explanatory enum variants can take `#[allow(missing_docs)]` on the enum.
- Re-run the MSRV check (`cargo +<msrv> check --workspace --all-targets --locked`) at the end:
  new code may use std APIs newer than the declared `rust-version`.
- Editing existing files: `write_file` refuses unless that file was fully read earlier in the same
  task (a read sent in the same parallel batch does not count; after a compaction even a fresh
  full read may not), and a refused write leaves the old file in place while later gates still
  pass. Prefer `patch` for existing files; for a scratch script or JSON you rewrite, write a new
  file name. Never launch a script in the same batch as its rewrite: a refused rewrite runs the
  old version (a commit-message or notes file too: the commit then carries the old text). Grep
  for the new content before building, capturing, running or committing.
- cargo-deny: `cargo deny init` takes no path and writes `deny.toml` in the current directory;
  build the licence allow-list from `cargo deny list -f tsv -l license` (crates offering
  `X OR MIT` pass through MIT). `allow-wildcard-paths` only covers unpublishable crates; give
  internal path dependencies a `version` instead. Ignore an advisory only with a `reason`.
- Licence files: copy `LICENSE-APACHE` verbatim from the most common copy in
  `~/.cargo/registry/src/*/*/LICENSE-APACHE` (group by hash) rather than typing it.
- When an item changes a log line that a harness or CI greps for (the smoke exit line), keep the
  grepped prefix or update the harness in the same commit.
- Toolchain bumps bring new clippy lints into code you touch. Fix them rather than allowing
  them:
  - `manual_is_multiple_of`;
  - `chunks_exact_to_as_chunks`: use `as_chunks::<3>().0`;
  - `double_ended_iterator_last`: use `next_back()`, which needs a `mut` binding;
  - `manual_pattern_char_comparison`: use `find(['=', '.'])`.
  - `needless_update`: after removing struct fields, a `..Self::default()` update may name
    every remaining field; drop the update.
- Python `Path.write_text` writes CRLF on Windows; generators should use
  `write_bytes(text.encode())` so regenerated assets don't diff on every line.
- Python edit scripts: write text that holds backslashes (ASCII art, regexes, Windows paths) as
  raw strings (`r"""..."""`): in a normal string a `\` at the end of a line silently joins it
  to the next line.
- Unattended runs: an approval prompt that times out blocks that action for the rest of the
  run. Inline interpreters (`python3 -c ...`) get flagged more often than a script file run as
  `python3 <file>`, so keep edit scripts in scratch files. PowerShell capture harnesses need
  the user at hand: when one is blocked, log the captures as not done and carry the item on
  headless tests.
- A user mentions "the image" or "the last screenshots" but the terminal has no attachment
  channel: list the newest files in their screenshot folder (this user: `~/Pictures/ekranoto`;
  otherwise `search_files` with `order="modified"` under `~/Pictures`) and look at them with
  `vision_analyze`, zooming with `region` on the spot that matters, before diagnosing; say which
  files you used. A pair taken while testing is often before and after a change the user
  toggled themselves: match each to the tree's state at its timestamp, or ask.
- After a change of geometry or viewpoint (camera angle, sizes, spawn spots), list every test
  that asserts a negative ("stays shut", "circle 0", "not hidden") and mutation-check it: its
  scenario may no longer reach the guarded code, so it passes without testing anything.
- A mutation check only counts when the test can see the mutation: one that changes behaviour
  outside the test's setup survives without proving anything. Mutate in the shape of the bug
  class the test guards, and name which other test covers what this one cannot.
- A non-default GPU path (another fade style, a debug view) is still worth one smoke run: flip
  the default in source with an asserted replace, run the smoke command, restore from a copy,
  and check `git diff` is empty for that file. Draw counts in the exit log show the path ran.
- Mutation checks: when two guards lead to the same early return (a cheap key check before an
  exact one), disabling one alone survives, because the other still returns. Mutate them
  together, or drop the redundant one. A guard whose mutation survives because nothing it
  excludes is ever drawn (a ray limit beyond the eye) is dead weight too: drop it, with a
  one-line why-comment, rather than write a test for an invisible difference.
- bevy_ecs: a `ParamSet` in a type alias (clippy's `type_complexity` asks for one) names its
  queries with `'static` lifetimes, `ParamSet<'w, 's, (Query<'static, 'static, ..>, ..)>`;
  with `'w`/`'s` inside it is not a valid system parameter.
- Committing an earlier state of files that the working tree has moved past: build that
  commit's files in a detached worktree (its own `CARGO_TARGET_DIR`), gate and commit there,
  then in the main tree `git reset --mixed <sha>`: the branch moves to the new descendant and
  the working tree keeps the later edits. Copy over any file the worktree changed that the
  main tree has not (the plan, the queue) before going on.
