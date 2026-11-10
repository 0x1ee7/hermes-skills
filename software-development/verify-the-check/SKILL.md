---
name: verify-the-check
description: "Use whenever a test, a diff or a measurement is about to be trusted: prove it can fail, that it ran on the code you meant, and that a zero is real."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [testing, verification, regression, mutation, workflow]
    related_skills: [perf-ab-testing, agent-referee-checks, engine-feature-delivery-loop]
---

# Verify the check before trusting it

A green test, an empty diff or an unchanged number only means something if the check could have
said otherwise. Each item below came from a check that passed for the wrong reason.

## When to Use

- A new regression test, before committing it.
- A comparison of two builds' outputs (pictures, numbers) that came out identical.
- A loosened bound, a test restored from an old copy, a guard written after the fix.

## Procedure

1. **Break it on purpose.** Disable the rule the test guards (force a flag, set a constant to zero,
   skip a branch), run the test, see it fail with a message that names the problem, restore. Keep
   the before and after numbers in the commit message.
2. **Check the test can see the change.** A test whose camera, sample region or scenario never
   reaches the changed code passes whatever the code does. Size the scene so the effect is inside it.
3. **Check the mutation applied.** Print the mutated line, or look for the compile line of the
   changed module, before reading the result. A replacement written for an earlier form of the file
   matches nothing.
4. **Check the build is the one you meant.** Restoring files from copies keeps the copies' times;
   build tools that compare modification times then skip the rebuild and both "variants" are one.
   Touch restored files. A command chain that fails early (`cd` failing in `a && b`) skips steps
   silently.
5. **Distrust a perfect zero.** Two builds that differ in code but give a bit-identical output: prove
   it by a deliberately broken build that moves the output. If that moves it, look for why yours
   did not (it may be genuinely unchanged, or never rebuilt).
6. **Keep bounds tight.** A bound loosened for an old failure hides the regression it was for; a test
   restored from an old copy brings its old bound. Hold it to the measured value plus margin.
7. **Drive state, don't set it.** A test that sets internal state by hand (a debt flag) does not show
   the code keeps it; run the frames or calls that would lose it.

## Verification

For every check relied on: it was seen to fail with the guarded behaviour removed, and seen to pass
with it restored, on a build shown to contain the change.
