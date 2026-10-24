"""Capture a game window with the player standing on a chosen tile, without PowerShell and
without touching other windows: a scratch asset root holds a copy of the level with the spawn
moved; the game starts with ISO_ASSET_ROOT pointing there, keys are posted to its own window,
and PrintWindow copies its client area into a PNG. Stdlib only (no Pillow).

    python capture-window.py <level> <x> <y> <out.png> [--wait S] [--exe PATH] [--turn Q|E SECONDS]

Adapt REPO, S, the map's spawn character and the manifest key layout to the project. The level
is a `level.<level>` key; the copy is loaded as `level.probe`. The game's log goes to <out>.log.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import shutil
import struct
import subprocess
import time
import zlib
from pathlib import Path

REPO = Path("D:/dev/iso-engine")
S = Path(os.environ.get("CAPTURE_SCRATCH", "C:/temp/capture"))
ASSETS = S / "assets"

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


def prepare(level, x, y):
    if not ASSETS.exists():
        shutil.copytree(REPO / "assets", ASSETS)
    shutil.copy2(REPO / "assets/manifest.ron", ASSETS / "manifest.ron")
    lines = (REPO / f"assets/maps/{level}.map").read_bytes().decode().split("\n")
    grid = [i for i, line in enumerate(lines) if line and not line.startswith("//")]
    end = next(i for i in grid if lines[i].startswith("["))
    rows = list(range(grid[0], end))
    for i in rows:
        if "@" in lines[i]:
            j = lines[i].index("@")
            beside = lines[i][j - 1] if j > 0 else lines[i][j + 1]
            lines[i] = lines[i][:j] + beside + lines[i][j + 1:]
    row = lines[rows[y]]
    assert row[x] not in "#=", f"({x}, {y}) is a wall"
    lines[rows[y]] = row[:x] + "@" + row[x + 1:]
    (ASSETS / "maps/probe.map").write_bytes("\n".join(lines).encode())
    manifest = (ASSETS / "manifest.ron").read_bytes().decode()
    at = manifest.index(f'"level.{level}":')
    manifest = manifest[:at] + '"level.probe": "maps/probe.map",\n        ' + manifest[at:]
    (ASSETS / "manifest.ron").write_bytes(manifest.encode())


def find_window(pid):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def each(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    return found[0] if found else None


def key(hwnd, vk, scan, down):
    # winit 0.30 maps the scan code in lParam to the physical key.
    lparam = 1 | (scan << 16) | (0 if down else (1 << 30) | (1 << 31))
    user32.PostMessageW(hwnd, 0x0100 if down else 0x0101, vk, lparam)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def grab(hwnd):
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    w, h = rect.right, rect.bottom
    screen = user32.GetDC(hwnd)
    dc = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, w, h)
    gdi32.SelectObject(dc, bitmap)
    user32.PrintWindow(hwnd, dc, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
    info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(dc, bitmap, 0, h, pixels, ctypes.byref(info), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(hwnd, screen)
    return w, h, pixels.raw


def write_png(path, w, h, bgra):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        row = bgra[y * w * 4:(y + 1) * w * 4]
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = row[2::4], row[1::4], row[0::4]
        raw += rgb

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    Path(path).write_bytes(png)


def main():
    args = argparse.ArgumentParser()
    args.add_argument("level")
    args.add_argument("x", type=int)
    args.add_argument("y", type=int)
    args.add_argument("out")
    args.add_argument("--wait", type=float, default=3.0)
    args.add_argument("--exe", default=str(REPO / "target/debug/demo.exe"))
    args.add_argument("--turn", nargs=2, metavar=("KEY", "SECONDS"))
    a = args.parse_args()
    prepare(a.level, a.x, a.y)
    env = dict(os.environ, ISO_ASSET_ROOT=str(ASSETS), ISO_EXIT_AFTER_FRAMES="1200")
    log = open(Path(a.out).with_suffix(".log"), "wb")
    game = subprocess.Popen([a.exe, "probe"], env=env, stdout=log, stderr=log, cwd=str(S))
    try:
        hwnd = None
        for _ in range(100):
            time.sleep(0.1)
            hwnd = find_window(game.pid)
            if hwnd:
                break
        assert hwnd, "no window"
        if a.turn:
            vk, scan = {"Q": (0x51, 0x10), "E": (0x45, 0x12)}[a.turn[0]]
            time.sleep(1.0)
            key(hwnd, vk, scan, True)
            time.sleep(float(a.turn[1]))
            key(hwnd, vk, scan, False)
        time.sleep(a.wait)
        w, h, bgra = grab(hwnd)
        write_png(a.out, w, h, bgra)
        print(f"captured {a.out} ({w}x{h})")
    finally:
        game.terminate()
        game.wait(10)
        log.close()


if __name__ == "__main__":
    main()
