---
name: agent-referee-checks
description: "Use to add tests that enforce a repo's architecture rules, agent files and task scope."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [integration-tests, architecture-tests, scope-check, agents-md, ci]
    related_skills: [agents-md-boundary-system, parallel-agent-task-protocol, parallel-agent-boundaries]
---

# Referee checks (any stack)

One test package that every boundary runs and only the `integration` boundary edits. It turns
the rules in AGENTS.md files into failures, so parallel agents cannot silently break each other.

## When to Use
- After `agents-md-boundary-system`, or when a rule keeps being broken by agents.
- Not for unit tests of a boundary's own logic.

## The five parts
| Part | Checks | How |
|---|---|---|
| architecture | each numbered root rule | parse manifests for dependencies (direct and transitive: `cargo tree`, `npm ls`, `pipdeptree`); scan sources for forbidden calls or imports, with an allow-list of files |
| boundaries | every member and area has an agent file; sections present and ordered; shim imports; one owner per file; every `owns` entry matches something; every `contract` item exists | read front matter; resolve ownership; grep public symbols or manifest keys |
| scope | with `AGENT_SCOPE` set, every file changed since `AGENT_BASE` is owned or shared by the scope | `git diff --name-only $BASE` plus untracked; `*` = integrator, unset = skipped; see `agents-md-boundary-system/scripts/scope_check.py` |
| pipeline | contracts that cross boundaries (data flows, fallbacks, interpolation) | tiny end-to-end fixtures, no window or network |
| scenarios | the real app, headless: every level, scene or fixture loaded and played | use the app's own entry point; assert invariants and frame-rate independence |

## Rules
- Failure messages name the file and line or entity, and say what to do. The reader is an agent
  with no context.
- Assert every discovered set is non-empty (members, sources, agent files, scenarios).
- **Mutation-check each test** before trusting it: back the file up, add one deliberate
  violation, see a failure naming the place, restore, see green. Do the same to the validator.
- The referee's own agent file lists every test and what its failure means; a test checks that.
- Pin the front-matter parser with its own test; every check reads through it.
- A known bug lands as an ignored test carrying the tracker ID; the fix removes the ignore.
- Helpers use the standard library only. Never edit the referee to make a change pass.
- `.hermes/` and `.claude/` (agents' scratch) are never a scope leak.
- Run three ways when changing the setup itself: default, `AGENT_SCOPE='*'`, and one single
  boundary (to see leaks listed with their owners).
