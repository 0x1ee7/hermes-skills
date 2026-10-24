"""Drive a game's window on Windows in the background: launch it without taking focus, post keys
and mouse input to its own window, capture its client area, compare captures. Python 3 stdlib
only (ctypes, zlib). Nothing here moves the real cursor, raises a window or reads the screen:
every call targets one window handle, so the user can keep working in other windows.

    python gamewin.py windows [--pid N] [--title TEXT]
    python gamewin.py launch [--cwd DIR] [--env K=V ...] [--log FILE] [--title TEXT]
                             [--activate] -- EXE [ARG ...]
        starts the game detached (it outlives this script), waits for its window and its first
        picture, and reports whether the focus moved
    python gamewin.py run (--pid N | --title TEXT | --hwnd H) [--tap-ms MS] STEP [STEP ...]
    python gamewin.py shot (--pid N | --title TEXT | --hwnd H) OUT.png
    python gamewin.py close --pid N [--timeout S]
    python gamewin.py diff A.png B.png [--threshold N] [--region X,Y,W,H]
    python gamewin.py tile OUT.png COLUMNS X,Y,W,H IN.png [IN.png ...]
    python gamewin.py keys

Steps, one command-line argument each (quote those with spaces):
    wait:S                  sleep S seconds
    tap:KEY[+KEY...]        press the keys in order, hold --tap-ms, release in reverse (Ctrl+S)
    hold:KEY[+KEY...]:S     the same, held S seconds
    down:KEY  up:KEY        press or release one key
    type:TEXT               one WM_CHAR per character, for text fields
    move:X,Y                the mouse to client pixel (X, Y)
    click:X,Y[:BUTTON]      left (default), right or middle click at (X, Y)
    dclick:X,Y              left double click
    drag:X1,Y1:X2,Y2[:S]    left button down at 1, moved to 2 over S seconds (0.3), released
    wheel:N[:X,Y]           N notches, positive away from the user (usually zoom in, scroll up)
    shot:FILE.png           capture the client area
KEY names are physical positions on a US keyboard, the scan codes games bind to; the window gets
the virtual-key code the current layout gives that position. `keys` lists the names.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import shlex
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

if sys.platform != "win32":
    raise SystemExit("gamewin.py drives windows on Windows only")

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LPARAM, WPARAM = ctypes.c_ssize_t, ctypes.c_size_t
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, LPARAM]
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.GetForegroundWindow.restype = wt.HWND
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsIconic.argtypes = [wt.HWND]
user32.IsWindow.argtypes = [wt.HWND]
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p,
                            ctypes.c_void_p, wt.UINT]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
kernel32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR,
                                                ctypes.POINTER(wt.DWORD)]

# Physical pixels everywhere, so client sizes, captures and mouse positions agree on a scaled
# display.
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor aware, v2
except AttributeError:
    user32.SetProcessDPIAware()

WM_CLOSE, WM_KEYDOWN, WM_KEYUP, WM_CHAR = 0x0010, 0x0100, 0x0101, 0x0102
WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0104, 0x0105
WM_MOUSEMOVE, WM_MOUSEWHEEL = 0x0200, 0x020A
BUTTONS = {  # down message, up message, double-click message, MK_ flag
    "left": (0x0201, 0x0202, 0x0203, 0x0001),
    "right": (0x0204, 0x0205, 0x0206, 0x0002),
    "middle": (0x0207, 0x0208, 0x0209, 0x0010),
}

# Physical keys: (scan code, extended, fixed virtual-key code or None to ask the layout).
KEYS = {}
for row, first in (("QWERTYUIOP", 0x10), ("ASDFGHJKL", 0x1E), ("ZXCVBNM", 0x2C)):
    for i, ch in enumerate(row):
        KEYS[ch] = (first + i, False, None)
for i, ch in enumerate("1234567890"):
    KEYS[ch] = (0x02 + i, False, None)
for i in range(10):
    KEYS[f"F{i + 1}"] = (0x3B + i, False, 0x70 + i)
KEYS.update({
    "F11": (0x57, False, 0x7A), "F12": (0x58, False, 0x7B),
    "Escape": (0x01, False, 0x1B), "Minus": (0x0C, False, None), "Equals": (0x0D, False, None),
    "Backspace": (0x0E, False, 0x08), "Tab": (0x0F, False, 0x09),
    "LBracket": (0x1A, False, None), "RBracket": (0x1B, False, None),
    "Enter": (0x1C, False, 0x0D), "LCtrl": (0x1D, False, 0x11),
    "Semicolon": (0x27, False, None), "Quote": (0x28, False, None),
    "Backquote": (0x29, False, None), "LShift": (0x2A, False, 0x10),
    "Backslash": (0x2B, False, None), "Comma": (0x33, False, None),
    "Period": (0x34, False, None), "Slash": (0x35, False, None),
    "RShift": (0x36, False, 0x10), "LAlt": (0x38, False, 0x12), "Space": (0x39, False, 0x20),
    "CapsLock": (0x3A, False, 0x14),
    "Numpad0": (0x52, False, 0x60), "Numpad1": (0x4F, False, 0x61),
    "Numpad2": (0x50, False, 0x62), "Numpad3": (0x51, False, 0x63),
    "Numpad4": (0x4B, False, 0x64), "Numpad5": (0x4C, False, 0x65),
    "Numpad6": (0x4D, False, 0x66), "Numpad7": (0x47, False, 0x67),
    "Numpad8": (0x48, False, 0x68), "Numpad9": (0x49, False, 0x69),
    "NumpadMultiply": (0x37, False, 0x6A), "NumpadPlus": (0x4E, False, 0x6B),
    "NumpadMinus": (0x4A, False, 0x6D), "NumpadPeriod": (0x53, False, 0x6E),
    "NumpadDivide": (0x35, True, 0x6F), "NumpadEnter": (0x1C, True, 0x0D),
    "RCtrl": (0x1D, True, 0x11), "RAlt": (0x38, True, 0x12),
    "Home": (0x47, True, 0x24), "Up": (0x48, True, 0x26), "PageUp": (0x49, True, 0x21),
    "Left": (0x4B, True, 0x25), "Right": (0x4D, True, 0x27), "End": (0x4F, True, 0x23),
    "Down": (0x50, True, 0x28), "PageDown": (0x51, True, 0x22),
    "Insert": (0x52, True, 0x2D), "Delete": (0x53, True, 0x2E),
    "LWin": (0x5B, True, 0x5B), "RWin": (0x5C, True, 0x5C), "Menu": (0x5D, True, 0x5D),
})
ALIASES = {"Esc": "Escape", "Return": "Enter", "Ctrl": "LCtrl", "Shift": "LShift",
           "Alt": "LAlt", "Control": "LCtrl", "Del": "Delete", "Ins": "Insert",
           "PgUp": "PageUp", "PgDn": "PageDown"}


def key(name):
    """(scan, extended, virtual-key code) of a key name, case-insensitive."""
    lookup = {k.lower(): k for k in KEYS} | {a.lower(): k for a, k in ALIASES.items()}
    found = lookup.get(name.lower())
    if found is None:
        raise SystemExit(f"unknown key {name!r}; `gamewin.py keys` lists the names")
    scan, extended, vk = KEYS[found]
    if vk is None:
        vk = user32.MapVirtualKeyW(scan, 1)  # MAPVK_VSC_TO_VK: what the current layout types
    return scan, extended, vk


# -- windows ---------------------------------------------------------------------------------


def text_of(fn, hwnd):
    buffer = ctypes.create_unicode_buffer(512)
    fn(hwnd, buffer, 512)
    return buffer.value


def pid_of(hwnd):
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def client_size(hwnd):
    rect = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    return rect.right, rect.bottom


def exe_of(pid):
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return "?"
    buffer, size = ctypes.create_unicode_buffer(1024), wt.DWORD(1024)
    ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    return Path(buffer.value).name if ok else "?"


def top_windows():
    found = []

    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(each), 0)
    return found


def matching(pid=None, title=None):
    """Visible top-level windows of `pid` or with `title` in their title, largest first; windows
    with no client area (message-only helpers) are left out."""
    hits = []
    for hwnd in top_windows():
        if pid is not None and pid_of(hwnd) != pid:
            continue
        name = text_of(user32.GetWindowTextW, hwnd)
        if title is not None and title.lower() not in name.lower():
            continue
        if pid is None and title is None and not name:
            continue
        w, h = client_size(hwnd)
        if w * h == 0:
            continue
        hits.append((w * h, hwnd))
    return [hwnd for _, hwnd in sorted(hits, key=lambda hit: -hit[0])]


def describe(hwnd):
    w, h = client_size(hwnd)
    pid = pid_of(hwnd)
    state = " minimized" if user32.IsIconic(hwnd) else ""
    return (f"hwnd {hwnd:#x} pid {pid} {exe_of(pid)} client {w}x{h}{state} "
            f"class {text_of(user32.GetClassNameW, hwnd)!r} "
            f"title {text_of(user32.GetWindowTextW, hwnd)!r}")


def target(args):
    if args.hwnd:
        hwnd = int(args.hwnd, 0)
        if not user32.IsWindow(hwnd):
            raise SystemExit(f"no window {hwnd:#x}")
        return hwnd
    if args.pid is None and args.title is None:
        raise SystemExit("name the window: --pid, --title or --hwnd")
    hits = matching(args.pid, args.title)
    if not hits:
        raise SystemExit("no visible window matches; `gamewin.py windows` lists them")
    return hits[0]


# -- launching and closing ------------------------------------------------------------------


def wait_for_window(proc, title, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        hits = matching(None if title else proc.pid, title)
        if hits:
            return hits[0]
        if proc.poll() is not None:
            raise SystemExit(f"the game exited with code {proc.returncode} before a window "
                             "appeared; see its log")
        time.sleep(0.1)
    raise SystemExit(f"no window after {timeout} s (a launcher may open the game under another "
                     "process: pass --title)")


def launch(command, cwd=None, env=(), log=None, title=None, activate=False, timeout=30.0):
    """Starts the game detached from this script, so it outlives it; returns (process, hwnd)."""
    environment = dict(os.environ)
    for pair in env:
        name, _, value = pair.partition("=")
        environment[name] = value
    info = subprocess.STARTUPINFO()
    if not activate:
        info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = 4  # SW_SHOWNOACTIVATE: the first window shows without focus
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
    out = open(log, "ab") if log else subprocess.DEVNULL
    before = user32.GetForegroundWindow()
    options = dict(cwd=cwd, env=environment, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                   startupinfo=info)
    try:
        # A new process group, out of the caller's job, so ending the caller ends nothing here.
        proc = subprocess.Popen(command, creationflags=0x200 | 0x01000000, **options)
    except OSError:  # the job forbids breaking away
        proc = subprocess.Popen(command, creationflags=0x200, **options)
    hwnd = wait_for_window(proc, title, timeout)
    shown = wait_for_picture(hwnd, timeout)
    now = user32.GetForegroundWindow()
    focus = "kept" if now == before else ("taken by the game" if now == hwnd else "moved")
    print(f"launched pid {proc.pid}; {describe(hwnd)}; focus {focus}; {shown}")
    return proc, hwnd


def wait_for_picture(hwnd, timeout):
    """Waits until the window shows more than one colour: games take a moment to draw."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if not user32.IsIconic(hwnd):
            _, _, rows, drawn = grab(hwnd)
            if drawn and not blank(rows):
                return f"first picture after {time.monotonic() - start:.1f} s"
        time.sleep(0.2)
    return (f"no picture after {timeout} s (one colour, such as a plain loading screen, "
            "counts as none)")


def close(pid, timeout):
    handle = kernel32.OpenProcess(0x00100000 | 0x0001, False, pid)  # SYNCHRONIZE | TERMINATE
    if not handle:
        print(f"pid {pid} is not running")
        return
    for hwnd in matching(pid):
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    if kernel32.WaitForSingleObject(handle, int(timeout * 1000)) == 0x102:  # WAIT_TIMEOUT
        kernel32.TerminateProcess(handle, 1)
        print(f"pid {pid} did not close within {timeout} s: terminated")
    else:
        print(f"pid {pid} closed")
    kernel32.CloseHandle(handle)


# -- input ----------------------------------------------------------------------------------


class Input:
    """Posts input to one window, remembering held keys and buttons."""

    def __init__(self, hwnd, tap_ms):
        self.hwnd, self.tap = hwnd, tap_ms / 1000.0
        self.alt = False
        self.buttons = 0
        self.at = (0, 0)

    def post(self, message, wparam, lparam):
        if not user32.PostMessageW(self.hwnd, message, wparam, lparam):
            error = ctypes.get_last_error()
            hint = " (the game runs elevated? UIPI blocks posts to it)" if error == 5 else ""
            raise SystemExit(f"PostMessage {message:#x} failed: error {error}{hint}")

    def key(self, name, down):
        scan, extended, vk = key(name)
        if vk == 0x12:
            self.alt = down
        system = self.alt or vk in (0x12, 0x79)  # Alt held, Alt itself, F10
        lparam = 1 | (scan << 16) | (extended << 24) | (self.alt << 29)
        if not down:
            lparam |= (1 << 30) | (1 << 31)
        message = (WM_SYSKEYDOWN if down else WM_SYSKEYUP) if system else (
            WM_KEYDOWN if down else WM_KEYUP)
        self.post(message, vk, lparam)

    def chord(self, names, seconds):
        names = names.split("+")
        for name in names:
            self.key(name, True)
        time.sleep(seconds)
        for name in reversed(names):
            self.key(name, False)

    def type(self, text):
        for unit in struct.unpack(f"<{len(text.encode('utf-16-le')) // 2}H",
                                  text.encode("utf-16-le")):
            self.post(WM_CHAR, unit, 1)
            time.sleep(0.01)

    def mouse(self, x, y):
        self.at = (x, y)
        self.post(WM_MOUSEMOVE, self.buttons, (y & 0xFFFF) << 16 | (x & 0xFFFF))

    def button(self, which, down, double=False):
        press, release, twice, flag = BUTTONS[which]
        self.buttons = self.buttons | flag if down else self.buttons & ~flag
        x, y = self.at
        message = twice if double else (press if down else release)
        self.post(message, self.buttons, (y & 0xFFFF) << 16 | (x & 0xFFFF))

    def wheel(self, notches):
        point = wt.POINT(*self.at)
        user32.ClientToScreen(self.hwnd, ctypes.byref(point))  # the wheel carries screen points
        delta = int(notches * 120) & 0xFFFF
        self.post(WM_MOUSEWHEEL, delta << 16 | self.buttons,
                  (point.y & 0xFFFF) << 16 | (point.x & 0xFFFF))


def point(text):
    x, y = text.split(",")
    return int(x), int(y)


def run(hwnd, steps, tap_ms):
    actor = Input(hwnd, tap_ms)
    start = time.monotonic()
    for step in steps:
        verb, _, arg = step.partition(":")
        parts = arg.split(":")
        verb = verb.lower()
        if verb == "wait":
            time.sleep(float(arg))
        elif verb == "tap":
            actor.chord(arg, actor.tap)
        elif verb == "hold":
            actor.chord(parts[0], float(parts[1]))
        elif verb in ("down", "up"):
            actor.key(arg, verb == "down")
        elif verb == "type":
            actor.type(arg)
        elif verb == "move":
            actor.mouse(*point(arg))
        elif verb in ("click", "dclick"):
            which = parts[1].lower() if len(parts) > 1 else "left"
            actor.mouse(*point(parts[0]))
            actor.button(which, True)
            time.sleep(actor.tap)
            actor.button(which, False)
            if verb == "dclick":
                actor.button(which, True, double=True)
                time.sleep(actor.tap)
                actor.button(which, False)
        elif verb == "drag":
            (x1, y1), (x2, y2) = point(parts[0]), point(parts[1])
            seconds = float(parts[2]) if len(parts) > 2 else 0.3
            actor.mouse(x1, y1)
            actor.button("left", True)
            for i in range(1, 11):
                time.sleep(seconds / 10)
                actor.mouse(x1 + (x2 - x1) * i // 10, y1 + (y2 - y1) * i // 10)
            actor.button("left", False)
        elif verb == "wheel":
            if len(parts) > 1:
                actor.mouse(*point(parts[1]))
            actor.wheel(float(parts[0]))
        elif verb == "shot":
            capture(hwnd, arg)
        else:
            raise SystemExit(f"unknown step {step!r}")
        print(f"{time.monotonic() - start:7.2f} s  {step}")


# -- captures -------------------------------------------------------------------------------


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG),
                ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


def grab(hwnd):
    """(width, height, RGB rows, whether PrintWindow drew) of the window's client area, whatever
    lies over it on screen."""
    w, h = client_size(hwnd)
    screen = user32.GetDC(hwnd)
    dc = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, w, h)
    gdi32.SelectObject(dc, bitmap)
    # PW_CLIENTONLY | PW_RENDERFULLCONTENT: also GPU-drawn content (DirectX, Vulkan, OpenGL).
    drawn = user32.PrintWindow(hwnd, dc, 3)
    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    pixels = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(dc, bitmap, 0, h, pixels, ctypes.byref(header), 0)
    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(dc)
    user32.ReleaseDC(hwnd, screen)
    bgra = pixels.raw
    rows = []
    for y in range(h):
        line = bgra[y * w * 4:(y + 1) * w * 4]
        rgb = bytearray(w * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = line[2::4], line[1::4], line[0::4]
        rows.append(rgb)
    return w, h, rows, bool(drawn)


def blank(rows):
    """One colour all over: nothing drawn yet, or a black capture."""
    return not rows or (all(row == rows[0] for row in rows)
                        and rows[0] == rows[0][:3] * (len(rows[0]) // 3))


def capture(hwnd, path):
    """Saves the window's client area as an RGB PNG."""
    if user32.IsIconic(hwnd):
        raise SystemExit("the window is minimized: a capture would be black, and many games "
                         "pause while minimized")
    w, h, rows, drawn = grab(hwnd)
    write_png(path, w, h, rows)
    warning = ("; WARNING: blank capture (not drawn yet, or the game draws elsewhere)"
               if blank(rows) or not drawn else "")
    print(f"captured {path} ({w}x{h}){warning}")


def write_png(path, w, h, rows):
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body)))

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(png)


def read_png(path):
    """(width, height, RGB rows) of an 8-bit, non-interlaced PNG: grey, RGB, with or without
    alpha (alpha dropped), any filters. Pure Python: a full-screen PNG with filters takes some
    seconds."""
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} is not a PNG")
    pos, idat = 8, []
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            w, h, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour)
    if depth != 8 or interlace or channels is None:
        raise SystemExit(f"{path}: only 8-bit, non-interlaced grey or RGB PNGs are read")
    raw, stride, n = zlib.decompress(b"".join(idat)), w * channels, channels
    rows, previous, i = [], bytearray(stride), 0
    for _ in range(h):
        kind, line = raw[i], bytearray(raw[i + 1:i + 1 + stride])
        i += 1 + stride
        if kind == 1:
            for x in range(n, stride):
                line[x] = (line[x] + line[x - n]) & 0xFF
        elif kind == 2:
            line = bytearray((a + b) & 0xFF for a, b in zip(line, previous))
        elif kind == 3:
            for x in range(stride):
                left = line[x - n] if x >= n else 0
                line[x] = (line[x] + ((left + previous[x]) >> 1)) & 0xFF
        elif kind == 4:
            for x in range(stride):
                a = line[x - n] if x >= n else 0
                b, c = previous[x], previous[x - n] if x >= n else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xFF
        previous = line
        if n == 3:
            rows.append(line)
        elif n == 4:
            rgb = bytearray(w * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = line[0::4], line[1::4], line[2::4]
            rows.append(rgb)
        else:
            grey = line[0::n]
            rgb = bytearray(w * 3)
            rgb[0::3] = rgb[1::3] = rgb[2::3] = grey
            rows.append(rgb)
    return w, h, rows


def diff(a, b, threshold, region):
    wa, ha, ra = read_png(a)
    wb, hb, rb = read_png(b)
    if (wa, ha) != (wb, hb):
        raise SystemExit(f"sizes differ: {wa}x{ha} and {wb}x{hb}")
    x0, y0, w, h = region or (0, 0, wa, ha)
    changed, largest, box = 0, 0, None
    for y in range(y0, y0 + h):
        row_a, row_b = ra[y][x0 * 3:(x0 + w) * 3], rb[y][x0 * 3:(x0 + w) * 3]
        if row_a == row_b:
            continue
        for x in range(w):
            d = max(abs(row_a[3 * x + c] - row_b[3 * x + c]) for c in range(3))
            if d > threshold:
                changed += 1
                largest = max(largest, d)
                px = x0 + x
                box = (px, y, px, y) if box is None else (
                    min(box[0], px), min(box[1], y), max(box[2], px), max(box[3], y))
    if not changed:
        print(f"no pixel differs by more than {threshold} levels in {w}x{h}")
        return
    print(f"{100 * changed / (w * h):.3f} % of {w}x{h} pixels differ by more than {threshold} "
          f"levels (largest {largest}); changes within x {box[0]}-{box[2]}, y {box[1]}-{box[3]}")


def tile(out, columns, region, inputs):
    x, y, w, h = region
    gap = 4
    count = len(inputs)
    lines = (count + columns - 1) // columns
    width, height = columns * w + (columns - 1) * gap, lines * h + (lines - 1) * gap
    canvas = [bytearray(b"\xff" * (width * 3)) for _ in range(height)]
    for i, path in enumerate(inputs):
        _, _, rows = read_png(path)
        ox, oy = (i % columns) * (w + gap), (i // columns) * (h + gap)
        for r in range(h):
            canvas[oy + r][ox * 3:(ox + w) * 3] = rows[y + r][x * 3:(x + w) * 3]
    write_png(out, width, height, canvas)
    print(f"tiled {count} crops into {out} ({width}x{height}), {columns} per row")


# -- command line ---------------------------------------------------------------------------


def region_of(text):
    values = tuple(int(v) for v in text.split(","))
    if len(values) != 4:
        raise SystemExit("a region is X,Y,W,H")
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    def with_target(sub):
        sub.add_argument("--pid", type=int)
        sub.add_argument("--title")
        sub.add_argument("--hwnd")

    listing = commands.add_parser("windows", help="list visible top-level windows")
    listing.add_argument("--pid", type=int)
    listing.add_argument("--title")
    start = commands.add_parser("launch", help="start a game without taking focus")
    start.add_argument("--cwd")
    start.add_argument("--env", action="append", default=[], metavar="K=V")
    start.add_argument("--log")
    start.add_argument("--title", help="wait for this title instead of the process's window")
    start.add_argument("--activate", action="store_true", help="let the window take focus")
    start.add_argument("--timeout", type=float, default=30.0)
    start.add_argument("game", nargs=argparse.REMAINDER, help="-- EXE [ARG ...]")
    steps = commands.add_parser("run", help="post steps to a window")
    with_target(steps)
    steps.add_argument("--tap-ms", type=float, default=60.0)
    steps.add_argument("steps", nargs="+")
    shot = commands.add_parser("shot", help="capture a window's client area")
    with_target(shot)
    shot.add_argument("out")
    stop = commands.add_parser("close", help="close a game, terminating it after a timeout")
    stop.add_argument("--pid", type=int, required=True)
    stop.add_argument("--timeout", type=float, default=5.0)
    compare = commands.add_parser("diff", help="compare two captures")
    compare.add_argument("a")
    compare.add_argument("b")
    compare.add_argument("--threshold", type=int, default=2)
    compare.add_argument("--region", type=region_of)
    tiles = commands.add_parser("tile", help="tile crops of captures into one PNG")
    tiles.add_argument("out")
    tiles.add_argument("columns", type=int)
    tiles.add_argument("region", type=region_of)
    tiles.add_argument("inputs", nargs="+")
    commands.add_parser("keys", help="list key names")
    args = parser.parse_args()

    if args.command == "windows":
        hits = matching(args.pid, args.title)
        for hwnd in hits:
            print(describe(hwnd))
        if not hits:
            print("no visible window matches")
    elif args.command == "launch":
        command = args.game[1:] if args.game[:1] == ["--"] else args.game
        if not command:
            raise SystemExit("launch needs the game's command after --")
        launch(command, args.cwd, args.env, args.log, args.title, args.activate, args.timeout)
    elif args.command == "run":
        run(target(args), args.steps, args.tap_ms)
    elif args.command == "shot":
        capture(target(args), args.out)
    elif args.command == "close":
        close(args.pid, args.timeout)
    elif args.command == "diff":
        diff(args.a, args.b, args.threshold, args.region)
    elif args.command == "tile":
        tile(args.out, args.columns, args.region, args.inputs)
    elif args.command == "keys":
        names = sorted(KEYS, key=lambda k: (len(k) > 1, k))
        print(" ".join(names))
        print("aliases: " + ", ".join(f"{a}={k}" for a, k in ALIASES.items()))


if __name__ == "__main__":
    main()
