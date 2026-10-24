---
name: game-window-control
description: "Use when driving or testing a game window on Windows."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [windows, games, testing, input, screenshots, automation]
    related_skills: [rust-game-backlog-execution, computer-use]
---

# Game window control (Windows)

Drive one game window in the background: launch the game without taking focus, post keys and
the wheel to its own window, capture its client area (GPU-drawn frames included), compare and
tile captures, close it. One stdlib Python script, `scripts/gamewin.py`: no PowerShell, no
Pillow, no driver. It never moves the real cursor, raises a window or reads the screen, so the
user can keep working while it runs.

## When to Use

- Checking a game you build: does a key do what it should, what does a spot look like, before
  and after a change, reproducing a user's screenshot.
- Running a single-player game through a short scenario the user asked for.
- Don't use for: online or multiplayer games (synthetic input can break their terms and trip
  anti-cheat: ask, and expect to decline); ordinary apps with buttons and fields (the
  `computer_use` tool of the skill `computer-use` reads their UI elements); games in exclusive
  fullscreen (switch them to windowed or borderless first).

## Prerequisites

- Windows 10 1703 or later, Python 3.8+ (stdlib only).
- The game runs at Hermes's integrity level or lower: an elevated game rejects posted messages
  (`PostMessage ... failed: error 5`).
- From Git Bash, pass native paths with forward slashes (`C:/...`); MSYS paths (`/c/...`) do
  not reach the native Python.

## How to Run

`skill_view` reports the skill's directory; call the script there:

```
terminal(command="python3 <skill_dir>/scripts/gamewin.py launch --cwd <game dir> --log <scratch>/game.log -- <game.exe> <args>", timeout=90)
terminal(command="python3 <skill_dir>/scripts/gamewin.py run --pid <pid> shot:<scratch>/a.png tap:Space wait:0.5 shot:<scratch>/b.png", timeout=120)
vision_analyze(image_url="<scratch>/b.png", question="...")
```

Keep captures in the scratch directory, never in the user's own screenshot folder: they find
their newest screenshots there by date.

## Quick Reference

```
windows [--pid N] [--title TEXT]            visible windows: hwnd, pid, exe, client size, title
launch [--cwd D] [--env K=V] [--log F] [--title T] [--activate] -- EXE ARG...
                                            start detached; wait for the window and a picture
run (--pid N|--title T|--hwnd H) [--tap-ms 60] STEP...
shot (--pid N|--title T|--hwnd H) OUT.png   capture the client area
close --pid N [--timeout 5]                 WM_CLOSE, terminate after the timeout
diff A.png B.png [--threshold 2] [--region X,Y,W,H]
tile OUT.png COLUMNS X,Y,W,H IN.png...      the same crop of each, side by side
keys                                        key names
```

Steps: `wait:S`, `tap:KEY[+KEY]`, `hold:KEY[+KEY]:S`, `down:KEY`, `up:KEY`, `type:TEXT`,
`move:X,Y`, `click:X,Y[:right|middle]`, `dclick:X,Y`, `drag:X1,Y1:X2,Y2[:S]`,
`wheel:N[:X,Y]`, `shot:FILE.png`. Coordinates are client pixels, the captures' pixels. Key
names are physical positions on a US keyboard (scan codes, which is what game bindings mean),
so `hold:W:1` walks forward on any layout; `type:` sends characters, for text fields.

## Procedure

1. **Get the window.** A running game: `windows --title <part of its title>`. Otherwise
   `launch`. Done when the line shows a client size, `focus kept` and `first picture after N s`.
   If it says `focus taken by the game`, the game raised itself: tell the user.
2. **Prove the input path once per game.** Two captures with no input between them give the
   noise (what animates by itself); a key with a visible effect between two more gives the
   signal: `run --pid N shot:n0.png wait:1 shot:n1.png shot:k0.png tap:<key> wait:0.5
   shot:k1.png`, then `diff n0.png n1.png` and `diff k0.png k1.png`. Done when the key's diff
   clearly exceeds the noise where the effect should be. A key whose effect is not on screen
   leaves no diff: confirm it through the game's log, if it writes one. No reaction at all: read
   Pitfalls before retrying.
3. **Script the scenario** as the steps of one `run`. Held keys move by wall-clock time, so
   plan distances from the game's speeds, then check in the capture where things ended up. Put a
   `shot:` wherever the question needs a picture.
4. **Look.** `vision_analyze` each capture, with `region` to zoom. To compare, `tile` the same
   crop of several captures into one image (a before row over an after row) and ask about each
   tile. Report what you saw and which file shows it.
5. **Close what you launched**: `close --pid N`. Done when it prints `closed` (or
   `terminated` after the timeout). A game started by `launch` outlives the call that started it.

## Verified

Against a winit 0.30 game (wgpu on Vulkan) on Windows 11, with its window unfocused:

| Input or call | Result |
|---|---|
| `launch` | shown without focus (`focus kept`); first picture after about 1 s; outlived the launching call |
| `launch`, ten times in a row | after the first, most runs reported `focus taken by the game`: batch captures into few launches and tell the user |
| keys: a letter, `W+Shift` held, a `Tab` tap, `F5`, `Up` (extended) | reached the game |
| `wheel` | reached the game (zoom) |
| `move` (hover) | no effect: the game's hover highlight never appeared |
| `click`, `dclick`, `drag`, `type` | posted without error; effect not checked (that game has no use for them) |
| `shot` | the Vulkan frame; blank before the first frame |
| `close` | the game closed through WM_CLOSE |
| `diff`, `tile` | read the script's captures and Snipping Tool PNGs |

Treat any other engine as unknown until step 2 passes, and add what you learn to this table.

## Pitfalls

- **Hover needs the real cursor.** With the real cursor elsewhere, posted moves did not count
  as hovering; the likely cause is the window's mouse tracking (`TrackMouseEvent`), which
  reports the cursor gone at once. Use keys and the wheel, or ask the user to place the cursor.
- **Raw input and polling.** A game that reads the keyboard through Raw Input, DirectInput or
  `GetAsyncKeyState`, or the mouse through Raw Input (most mouse-look cameras), ignores posted
  messages: step 2 shows nothing beyond the noise. The script has no foreground mode on
  purpose: real input (`SendInput`) needs the window in front and the user's hands off the
  machine, so it is the user's call, never a silent fallback.
- **Paused when unfocused.** Some games stop updating without focus: things that should
  animate don't, and keys do nothing. Look for a "run in background" setting, or ask.
- **Modifiers.** Posted Shift, Ctrl and Alt reach games that track key messages; a game that
  asks `GetKeyState` sees the real keyboard instead.
- **Minimized windows** capture black, and many games pause while minimized. Never restore or
  raise a window yourself: ask.
- **Launchers.** When a launcher starts the real game as another process, pass `--title` to
  `launch` so it waits for the game's window.
- **Taps** last 60 ms (`--tap-ms`): two frames or more at 30 fps.
- **The game keeps running** after a `run`. Close it, and set the game's own safety exit if
  it has one (a frame-count environment variable, for example).
- **Sound.** A driven game plays through the user's speakers while they work. Launch it with
  its mute switch when sound is not what you check (`--env ISO_AUDIO=0` for the iso engine);
  check audio headlessly instead, or leave the listening to the user.

## Safety (hard rules)

- Never call `SendInput`, `keybd_event`, `mouse_event`, `SetCursorPos`, `SetForegroundWindow`
  or `BringWindowToTop`, and never capture the screen (`CopyFromScreen`, a desktop `BitBlt`):
  they act on whatever the user has in front.
- Only games the user builds or owns and plays offline; ask before touching anything online.
- Never type passwords or keys, and don't drive launchers, stores, purchase or login dialogs.

## Verification

Done when `launch` (or `windows`) found the window with `focus kept`; step 2 showed a key's
effect beyond the noise, or in the game's log; the captures that answer the question were looked
at with `vision_analyze`; `close` reported `closed`; and anything new about this engine's input
is in **Verified**.
