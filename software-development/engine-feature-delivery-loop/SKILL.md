---
name: engine-feature-delivery-loop
description: "Use for a multi-crate engine feature: plan, fix prerequisites, implement, verify, document, commit."
version: 1.0.0
author: omp
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [workflow, planning, rust, engine, documentation, commits, review]
    related_skills: [rust-game-backlog-execution, roadmap-and-handoff-docs, agents-md-boundary-system, parallel-agent-boundaries]
---

# From request to committed engine feature

The loop used for "analyse, plan the prerequisites, fix them, then implement shadows and GI" across math, core, render, platform and demo crates with per-boundary agent files and an integration suite.

## When to Use

- A feature crosses crate boundaries and the code base has structure debt that the feature would worsen.
- The repo has agent files, a roadmap and a handoff doc that must stay true.

## Loop

1. **Read, do not guess.** Root and boundary agent files, roadmap, handoff, then the renderer's reading order; use `grep` for each symbol you will change (contract items!). Map: what is duplicated, what is constant, where the pass structure forbids the feature.
2. **Write the plan file first** (`.hermes/plans/<date>_<name>.md`): findings, prerequisites table (ID, fix, where), features, order. Add the roadmap row *before* code (repo rule). Keep the plan's shape; details (API names, vertex formats) are settled while implementing.
3. **Prerequisites, one verified step at a time**: settings in the core crate (default off so goldens stay), shared shader files composed per module and validated with naga, shared bind-group layouts, stage structure before the main pass, extraction of what the feature needs, stats. Each step: `cargo fmt`, `cargo check --tests`, targeted tests. Run the golden image after each; defaults must leave it unchanged.
4. **Feature in slices that each render something**: shadows (look at the PNG) -> sky occlusion -> bounce. Throwaway scene to see it, then permanent assertions.
5. **Tests that mean something.** Make logged GPU errors fail GPU tests (a counting `log::Log`; wgpu validation errors otherwise vanish). Prefer world-anchored oracles (an open-field pixel equals the plain render, scene run at the origin and 40 m away) over comparing two renders of the same code, which cancels a self-consistent bug. Mutate the guard on purpose and see the test go red.
6. **Demo wiring** last: default on plus keys to toggle (add keys to the core `Key` enum and the platform map, update the platform key test), order systems that write the same resource (`.after(..)`) so the ambiguity warning stays at zero. Game-tunable looks (sun colour, view-light warmth, edge softness) live in settings and the uniform, never WGSL constants.
7. **Docs in the same change**: boundary agent files (contract list, provides, uses, invariants, tests, known issues, reading order with line counts from `wc -l`), `docs/architecture.md`, README keys, roadmap Done row + remaining fixes, handoff Next, plan "Result" with smoke numbers.
8. **Gates** chained with `&&`: fmt check, clippy `-D warnings`, doc `-D warnings`, `AGENT_SCOPE='*' AGENT_BASE=HEAD cargo test --workspace`, the repo's generated-file checks. Then a real run of the game (launch, toggle keys, capture, diff, close; check the exit smoke log).
9. **Commit** after the user's look when the change is visible; if they say "continue autonomously", commit and say so. No co-author trailer, no git commands used just to validate.

## Triage of review feedback

Aggregated advisories arrive late and are sometimes about code that no longer exists. For each: is it still true in the current tree? Is it cheap? Act on valid ones (error logger for swallowed GPU errors, a blind test, a contract re-export, a hard-coded tunable), reject the rest silently. If the code already does what the advisory asks (soft edge in metres), say so in one line.

## Rules

- Interface changes (removed `light_direction`) migrate every caller in the same change.
- Contract items in an agent front matter must name public items that exist; the boundaries test will tell you.
- Report what you ran. Do not claim visuals you have not looked at.
