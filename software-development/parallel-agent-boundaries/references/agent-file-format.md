# Agent file format

## Boundary file (`<boundary dir>/AGENTS.md`)

The referee reads the front matter, so keep it strict. Values are comma-separated, a line
starting with a space continues the key above, and `#` starts a comment, on a line of its own
or after the values (no path, crate or item name contains `#`). Unknown keys are errors.

```
---
boundary: engine_core                   # the name AGENT_SCOPE uses
package: engine_core                    # the Cargo package (crates only)
owns: crates/engine_core/               # a trailing / owns everything below; otherwise one file
shares: docs/architecture.md            # editable without owning it
depends: engine_assets, engine_math     # workspace crates in [dependencies]
external: bevy_ecs, glam                # other crates in [dependencies]
dev-depends:                            # everything in [dev-dependencies]
forbidden: engine_render, wgpu, winit   # never in any dependency section
never-in-tree: wgpu, winit              # never in the resolved dependency tree
contract: App, App::update, Transform   # public items others use (content: manifest keys)
---
```

Next comes a title and one paragraph: what the boundary is, which repo rules matter most here,
and "Read the root AGENTS.md first". The sections follow in the order below.
Extra sections, such as Known issues, may go between them.

- **Scope**: what the boundary owns and may edit, what counts as an interface change here, and
  where new things of each kind belong.
- **Provides**: a table with the columns `Items | Notes | Used by`, or bullets grouped by kind.
  Every contract item appears here, and the users are named for each item.
- **Uses**: for each other boundary, the items used; external crates with their versions.
- **Invariants**: one bullet each, ending with the test or referee part that guards it.
- **Tests**: the command and the test count, the referee parts that cover this boundary, and
  what needs a GPU or a window.
- **Known issues**: IDs from the project's improvement register, one line each. Say where the
  fix belongs when that is another boundary.
- **Reading order**: files with their line counts, and where the tests start in long files.

Non-code boundaries (content) have no `package`, and their `contract` lists the manifest keys
that code names. A sub-folder with its own tooling gets a short `AGENTS.md` without front
matter that points at its boundary's file, with a table of tool, what it writes, what it needs
and how to check it.

## CLAUDE.md shim

Put one beside every `AGENTS.md`, the root one included, so that Claude Code loads the same
text:

```
Claude Code reads this file; the guide that every agent shares is [AGENTS.md](AGENTS.md),
imported here:

@AGENTS.md
```

Use visible text rather than an HTML comment: a person who opens the file sees where the rules
went, and no line passes 100 characters. The root `CLAUDE.md` becomes this shim too, once its
text has moved into the root `AGENTS.md` word for word. Never keep the rules in `CLAUDE.md`
behind a pointer to `AGENTS.md`: once an `AGENTS.md` exists, Hermes no longer loads
`CLAUDE.md` (`agent-context-files`).

## Root AGENTS.md

The front matter has `boundary: workspace`, and `owns:` lists the root files, `docs/`, CI and
the diagram generator. Then come the title and the old root `CLAUDE.md` text word for word: its
intro, **Commands** (plus the referee command) and **Rules**. The referee requires these five
sections after them, in this order:
1. **Boundaries**: a table (boundary, agent file, owns, uses), plus the dependency direction.
2. **Context**: what to load and what to leave out.
   - Always load: the root file and your own boundary's file. Hermes and Codex merge the
     `AGENTS.md` files from the repo root down to the cwd, so an agent started in the
     boundary's folder gets both; Claude Code loads a folder's `CLAUDE.md`, and with it the
     `AGENTS.md`, when it reads files there.
   - From other boundaries: only their Provides section.
   - Leave out: generated and binary files, the lockfile, `target/`.
   - The size of each boundary, tests included.
3. **Parallel work**: the protocol below.
4. **Integration suite**: a table (part, what it checks), with `AGENT_SCOPE` and `AGENT_BASE`.
5. **Agent file format**: the front matter block and the section order.

The protocol, numbered in the file:
1. A task names its scope (`AGENT_SCOPE`) and its base commit (`AGENT_BASE`). Most tasks have
   one boundary.
2. Isolate the task: `git worktree add ../<repo>-<task> -b agent/<task> <base>`, plus a
   `CARGO_TARGET_DIR` of its own. Parallel builds otherwise queue on one lock. On a drive that
   cannot hard-link, put the target directory on NTFS.
3. Edit only what the boundary owns or shares. Read anything. The boundary's own `AGENTS.md`
   belongs to it: keep it true in the same change as the code.
4. Adding public items is fine; list them under `contract`. Removing or renaming an item, or
   changing what it means, is an interface change.
5. When a task needs something from another boundary, it puts an interface request in the
   hand-off: the boundary, the need, why, and the proposed signature. Work around it only if the
   workaround is small and easy to delete.
6. Workspace files (manifests, the lockfile, CI, root docs, queue files) belong to the
   integrator.
7. Before the hand-off, run:
   - the fmt check;
   - clippy with `-D warnings`;
   - the boundary's own tests;
   - `AGENT_SCOPE=<b> AGENT_BASE=<base> cargo test -p integration_tests`.

   A red referee test outside the boundary means a broken contract. Fix it inside the scope or
   explain it. Never edit the suite.
8. Write the hand-off note:
   ```
   Task: <ID or title>      Scope: <boundaries>      Base: <commit>      Branch: agent/<task>
   Changed: <files or areas>
   Contract: none | added <items> | interface request: <boundary, need, why, proposed signature>
   Tests: <added or changed tests; which failed before the change>
   Verified: <commands run, all green>      Not verified: <what, and why>
   For the integrator: <shared docs, queue entries, dependencies to update>
   ```
9. The integrator merges one branch at a time:
   - rebase it onto main;
   - run every gate, the suite with `AGENT_SCOPE='*'`, and the smoke runs;
   - then update the shared docs, the queue files and the agent files of any interface change.

Tasks can run side by side when their scopes don't overlap and neither changes a contract the
other uses. A task that crosses several boundaries runs alone, or is split into an engine task
followed by a game task.

## Style

Use short, plain sentences. Every fact that a test checks names the test, and sizes and counts
come from commands. Refer to the repo's rules by number instead of restating them. Leave out
anything an agent from another boundary does not need. Keep the root file plus the largest
boundary file under the cap Hermes applies on every path: `context_file_max_chars` from its
config.yaml (this user: 40,000), else 20,000, what subagents always get.
