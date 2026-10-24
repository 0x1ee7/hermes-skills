---
name: game-footstep-banks
description: "Use when a game needs footstep or impact one-shot banks."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [audio, footsteps, sound-design, one-shots, dsp, numpy, ffmpeg, game-assets]
    related_skills: [cc0-sound-sourcing, rust-game-backlog-execution]
---

# Footstep and impact banks for a game

A game plays one short file per footfall, picked from a bank of variants per surface, every
stride and every 0.15 s at a run. The files must be dry one-shots that stack without turning
into echo, must be told apart by surface, and must not sound synthetic. Worked out on iso-engine
(`tools/cut_steps.py`, `tools/gen_placeholder_sounds.py`, `docs/sounds.md`) over three
listening rounds: "a long echoing tail", "very high pitch and unrealistic", "good but still
fabricated"; real recordings cut to single contacts ended it.

## When to Use
- Footsteps, impacts, shots: anything triggered by the simulation at a rate that overlaps.
- A user hears synthesised effects as harsh, high, echoing or fake.
- Don't use for music or ambiences (loops, not one-shots).

## The rules a one-shot must meet (and why)
- One strike: a rise of 6 dB within 10 ms to above -24 dB of the file's loudest 5 ms, with no
  second such rise 35 ms or more later. A heel and a toe in one file gallop at a run; a
  synthesised "heel then toe" was heard as echo.
- 40 dB down from 0.25 s on (steps) or 0.5 s (shots), silent (-60 dB) over the last 20 ms:
  tails pile up when a sound repeats every 0.15 s.
- Mono, no room: space, distance and reverb are the engine's.
- Level by loudness, not peak: the RMS of the loudest 20 ms at -18 dBFS (soft surfaces -20,
  shots -12), peak capped at 0.85. Peak normalising makes clicky surfaces quiet and noisy ones
  loud.
- Encode the rules in the asset tests (engine_assets' `every_manifest_sound_is_one_dry_strike`
  is the model) and in the tool that writes the files, so a bad file is refused at once.
- Write the Rust rules once, as methods on the engine's sample type (`levels_5ms`, `strikes`,
  `quiet_after(seconds)`, `ends_silent`), and have every crate's test call them: two test
  modules that each roll their own 5 ms windows drift apart (one judged the tail by overall RMS
  against the peak, the other per window against the loudest window) and nobody notices until
  an audit. The Python cutter mirrors them by necessity; keep the constants identical. Test
  the methods on synthetic 10 ms bursts (two bursts are two strikes, one dies away, a tone
  never does, a second burst within 30 ms is the same strike); a strike's time is its 5 ms
  window's start (220 samples at 44.1 kHz, not exactly 5 ms), so compare times with one
  window of tolerance, never for equality.
- When the banks come from recordings, retire the synthesis generator in the same queue:
  left in place it keeps a vacuous `--check` in CI, an import in the asset-list tool and a
  placeholder paragraph in every sound doc. Git history is where the synthesis lives on.

## Measure before and after (`scripts/measure.py <folder>`)
- Per file: length, peak, loudest-50 ms RMS, A-weighted spectral centroid, 85 % roll-off,
  share above 4 and 8 kHz, below 300 Hz, -40 and -60 dB times, strikes (the rule above).
- Measure A-weighted. A 60-100 Hz thump holds 90 % of a step's raw power while the ear barely
  weighs it; raw centroids of 0.1-0.5 kHz hid files the user heard at 2.4-5.6 kHz.
- Real steps, A-weighted: metal and wood thuds 0.3-0.5 kHz, concrete and rock 0.7, dirt, gravel,
  tile, snow, ice, asphalt 1.2-1.9, grass 2.5, splashes 3.2 kHz (half their energy above 4 kHz
  and still right).
- Distinctness: 16 log-spaced A-weighted band energies in dB (smoothed over neighbours, floored
  at -40 dB) plus 40 x the -40 dB time; the smallest distance between two surfaces should
  exceed the largest spread within one surface's variants. Only a guide for recordings: real
  steps vary more than synthesis, and the ear separates them by texture anyway.
- Listening preview: `scripts/preview.py <folder> out.wav` lays every bank out walking, then
  the shots, then runs 0.15 s apart on three surfaces; check the run's peak for clipping. Leave
  before/after previews in scratch for the user; their ears decide, and the project's rule
  ("what the user can hear waits for their listen before it is committed") stands.
- ffmpeg's `showspectrumpic` with `fscale=log` draws a false horizontal line (~755 Hz);
  confirm anything odd with an FFT of the tail.

## Cutting banks from recordings (`scripts/cut_contacts.py`)
- Source a walking sequence per surface (the `cc0-sound-sourcing` skill), decode to 44.1 kHz
  mono 16-bit with ffmpeg, then
  `uv run --with numpy python cut_contacts.py src.wav out step_gravel --keep 5 [--loud -18]
  [--whole] [--max 260] [--tail 250] [--gap 250] [--from S --to S] [--list]`.
- What it does: contacts by the strike rule over the whole file; contacts within `--gap` ms are
  one step (heel, toe); a slice runs from 3 ms before the heel to 8 ms before the toe (or
  `--max`), with a 30 ms fade into the cut and 25 ms of silence after it (a fade that ends at the
  file's end leaves the last 20 ms audible); within the slice a second strike by the slice's own
  measure is a toe that was too quiet to count file-wide: cut there too. High-pass at 30 Hz.
  `--whole` keeps crunches and splashes past the toe and damps the slice exponentially after
  30 ms only when a later grain still counts as a strike (gravel, snow, ice, water, shots).
- Selection: slices near the median raw loudness (not stomps or scuffs) with a floor 10 dB
  below them, then nearest the median band spectrum, spread over the recording. Picking the
  loudest contacts picks scuffs and toe slaps; a single loud outlier wrecks a "within 12 dB of
  the loudest" filter, so widen the window stepwise when too few remain.
- Shots: `--whole --max 600 --tail 500 --gap 1500 --loud -12`; a close 9 mm recording's
  slapback needs the damping and a fade to -40 dB by 0.5 s. Keep designed or Audacity-made
  shots out.
- Heel-only cuts are 90-250 ms; hard surfaces 90-120 ms. That is a complete "step" sound
  (Kenney's are 100 ms). If a walk needs the toe, play it as a second, quieter sound from the
  engine a stride-dependent time later; do not put it back in the file.
- Keep the recipe (source id, author, licence, cut settings per bank) in a standard-library
  module of its own that the cutter and the asset-list tool both import, with a `--credits`
  printer and a `--check-credits` that CI runs against `CREDITS.md`; a recipe inside the numpy
  cutter forces other tools to regex its source. Cut into the asset folder, commit the cuts
  (numpy is not byte-exact across versions, so no `--check`), let the asset tests hold them.
  Grep tests for the old variant count: one assumed `Some(3)` variants.

## Synthesising a placeholder when no recording exists
Standard-library Python, deterministic, with a byte-exact `--check` in CI (run it under WSL
before pushing: libm differs). What made synthesis less harsh, in order of effect:
- Noise bursts whose low-pass cutoff falls over a few ms (bright onset, then dark) instead of
  flat bands reaching 7-14 kHz; a one-pole low-pass at 6 kHz over the whole mix.
- A heel thud (damped sine 150-270 Hz, 9-16 ms) and a body thump (60-100 Hz, 30-40 ms time
  constant: files need 0.22-0.34 s to reach -60 dB).
- Textures as shaped grain clouds: damped-sine ticks (1.4-4.8 kHz, 1-2 ms) for stones, low-passed
  puffs for snow, a few crumbs for earth, a plate rattle 9 ms after the heel for metal, each
  building for ~20 ms and trailing off exponentially; a span that simply ends is heard as a cut.
- Loudness levelling (above) and the rules built into `finished()` so the script refuses a
  second strike or a long tail.
It still sounded fabricated to the user; treat it as a stopgap and go to recordings.

## Files
- `scripts/measure.py`: the per-file table and the distinctness summary (numpy).
- `scripts/cut_contacts.py`: cut a recording into single-contact one-shots (numpy).
- `scripts/preview.py`: a listening preview WAV from a folder of banks (standard library).
