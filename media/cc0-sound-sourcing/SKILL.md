---
name: cc0-sound-sourcing
description: "Use when a project needs CC0 sound recordings fetched."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [audio, sound-effects, cc0, freesound, kenney, opengameart, licensing, game-assets]
    related_skills: [game-footstep-banks, rust-game-backlog-execution]
---

# Sourcing CC0 sound recordings

Real recordings beat synthesis once a user calls generated sound "fabricated". For a public
repository the licence must allow redistribution: Creative Commons 0 is the safe choice
(CC-BY works with credit; royalty-free bundles such as Sonniss allow a shipped game but not
passing the files on). Three libraries are reachable from a terminal with no account or API key.

## When to Use
- Footsteps, impacts, shots, ambiences or any effect for a game or video that will be published.
- Don't use for: music (different licensing world), anything a user may only use privately.

## Freesound (the largest; no key needed)
- Search and sound pages are public HTML. `scripts/fs.py search footsteps gravel` lists CC0
  results (id, duration, author, title) by adding `f=license:"Creative Commons 0"` and reading
  each result's `data-sound-id`, `data-username`, `data-title`, `data-duration` attributes
  (the `bw-player` divs; match `class="bw-player[^"]*"`, the attributes span lines).
- `scripts/fs.py info <id>` reads the sound page: canonical URL, the licence link
  (`creativecommons.org/publicdomain/zero/1.0/` is CC0), description, author, and the pack link
  (`/people/<user>/packs/<id>/`). One recordist's pack across surfaces (Nox_Sound's "Footsteps")
  gives coherent banks; list a pack's sounds from its page the same way.
- `scripts/fs.py get <id> ...` verifies CC0 on the page, then downloads the HQ preview: the
  original file needs a login, but the preview (`-hq.ogg`, OGG Vorbis ~192 kb/s, often 48 kHz)
  sits on the public CDN at the URL the page's `data-ogg` gives with `-lq.` swapped for `-hq.`.
  For sub-second effects the preview is transparent. Decode with ffmpeg:
  `ffmpeg -i x.ogg -ac 1 -ar 44100 -c:a pcm_s16le x.wav`.
- Searching is fuzzy and sometimes returns nothing for a term that has results; retry with
  other words ("walking on ice" found what "footsteps ice" did not) and pause 2-5 s between
  requests. `search` with `username:"X"` misses sounds; a user's pack page is reliable.
- Prefer walking sequences (10-60 s) to single-step files: one recording yields many
  consistent variants (the `game-footstep-banks` skill cuts them).

## Kenney (CC0 packs)
- The asset page (`https://kenney.nl/assets/<pack>`) holds the zip link in its download
  dialog: `grep -oE "href='https://kenney.nl/media/pages/assets/[^']+\.zip'"`. The zip's
  `License.txt` states CC0. Impact Sounds: footsteps on concrete, grass, snow, wood, carpet
  (5 each, OGG), plus metal, plate, tin, wood, glass impacts. Its concrete, grass and wood
  steps are single strikes; its snow steps are 3-5 grains and its plates ring half a second.

## OpenGameArt (CC0 filter)
- Advanced search: `art-search-advanced?keys=<words>&field_art_type_tid[]=13` (audio)
  `&field_art_licenses_tid[]=4` (CC0). A page's licence sits in `field-name-field-art-licenses`,
  the author in `field-name-author-submitter` ("Submitted by"), files as direct
  `/sites/default/files/...` links (zip, 7z, wav, ogg, flac). `scripts/ogainfo.py <saved
  page.html>` prints title, author, licence, body. Windows' `C:\Windows\System32\tar.exe`
  (bsdtar) extracts 7z when no 7z binary is installed.
- Some uploads are re-uploads of Freesound packs with the original author named in the body
  (Fantozzi's footsteps, submitted by qubodup): credit the original author.

## Vetting
- Read every description before using a sound. In one pass three of sixteen "footsteps" were
  fakes: a microphone stuffed in a wallet and poked with a pen, a walk over a pile of ice
  cubes, a pistol shot "artificially created with Audacity". Synthesised uploads (Vitalium,
  Audacity) are not recordings.
- Check what the title promises against the body: "metal footsteps on concrete" was a metal
  foot on concrete, "wet footsteps" a puddle, "earthy footsteps" the wallet.
- Measure before choosing (the `game-footstep-banks` skill's `measure.py`): length, strikes
  per file, noise floor between steps, A-weighted centroid. Quiet recordings (raw steps at
  -35 dBFS) still work if the floor is 15 dB below them.

## Crediting
- Keep a `CREDITS.md` in the asset tree: file(s), source link (`https://freesound.org/s/<id>/`),
  author, licence, and what was done to the recording (cut, faded, levelled). CC0 needs no
  credit, but give it; CC-BY requires it.
- Keep the recipe (source id, URL, author, licence, cut settings) in the tool that produces the
  files, so credits and files come from one place (`--credits` prints the table).
- Pixabay and Zapsplat forbid redistributing files as files: not for a public repository.

## Files
- `scripts/fs.py`: `search <words>`, `by <user> <words>`, `info <id>`, `get <id>...` (verifies
  CC0, saves `dl/fs/<id>.ogg` and `<id>.json` with title, author, licence, URL, description).
- `scripts/ogainfo.py`: facts from saved OpenGameArt pages (title, author, licence, body).
