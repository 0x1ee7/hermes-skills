---
name: perf-ab-testing
description: "Use when deciding whether a code change makes a real-time program (a game, a renderer) slower or faster: interleaved A/B runs, a noise floor, quantiles over thresholds, and the traps that fake a result."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [performance, benchmarking, games, rendering, measurement]
    related_skills: [verify-the-check, game-window-control, engine-feature-delivery-loop]
---

# A/B testing frame time

A timing claim is the difference between two builds measured the same way, at the same time, on
the same machine state, larger than the difference between two runs of one build.

## When to Use

- Before committing a change meant to make frames cheaper, or one that might make them dearer.
- When asked whether a branch is "worse than main".
- When a single run's number looks like a win or a loss.

## Procedure

1. **Two named binaries, both fresh.** Build each variant and copy the binary to a distinct name.
   Check the build log said it finished and that the binary's time is newer than the edits: a
   failed `cd` in a `&&` chain, or a restored file with an old modification time, leaves the build
   tool reusing an old binary.
2. **Baseline from the committed tree**, not a binary built earlier from other code. For another
   branch or a bisect point, use a separate worktree and its own build directory.
3. **Interleave and swap.** A B, B A, A B ...; three pairs or more. Never all of A then all of B:
   clocks, heat and background load drift over minutes.
4. **Know the noise.** Run the same build twice (a control). A difference inside that spread is no
   difference.
5. **Quiet machine.** No builds, tests or other agents during runs; your own compile can cause
   30 to 80 ms stalls that look like the program's.
6. **Measure distributions, not one number.** Log every frame; report mean, p95, p99, and frames
   over a bound well above the steady frame (1.5 times the vblank). A count over a bound that the
   steady frame sits near measures drift, not dips.
7. **Per-stage costs on a fixed view.** Averages over a scripted walk are weighted by how many
   frames each build draws where: the build that drops frames in heavy views averages fewer heavy
   views and looks cheaper. Compare stage times standing still, and confirm both draw the same.
8. **Read the outliers.** A long frame whose own stages add up to a fraction of it is outside
   interference; one whose GPU stage is long is the program.

## Pitfalls

- Log files that append across launches mix runs: truncate per run, or split on the launch marker.
- Lower work can lower GPU clocks and make a pass read slower per frame; compare at equal load or
  on a still view.
- A change can trade cost for picture: measure the output too (`verify-the-check`), not only time.

## Verification

Done when both binaries are shown fresh, the pairs are interleaved, the control spread is known,
and the reported difference (quantiles, stage on a still view) exceeds it.
