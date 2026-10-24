"""Lay a folder of one-shot banks out as one listening preview (standard library).

    python3 preview.py <folder> <out.wav> [material ...]

Banks are step_<material>_<n>.wav (every n found) and gun_shot_<n>.wav. Each material's
variants 0.5 s apart, 0.6 s between materials (in the order given, else alphabetical), then the
shots 1.2 s apart, then runs of eight steps 0.15 s apart on the first three materials: the
pile-up a running player makes. Prints the peak; clipping shows as a peak at 1.0.
"""
import re
import struct
import sys
import wave
from pathlib import Path


def load(path):
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())
    return rate, [v / 32768.0 for v in struct.unpack(f"<{len(frames) // 2}h", frames)]


def main():
    folder, out = Path(sys.argv[1]), Path(sys.argv[2])
    banks = {}
    for path in sorted(folder.glob("step_*_*.wav")):
        m = re.match(r"step_(.+)_(\d+)$", path.stem)
        banks.setdefault(m.group(1), []).append(path)
    order = sys.argv[3:] or sorted(banks)
    shots = sorted(folder.glob("gun_shot_*.wav"))
    rate, mix = None, []

    def place(at, path):
        nonlocal rate
        r, s = load(path)
        rate = rate or r
        assert r == rate, path
        first = int(round(at * rate))
        need = first + len(s) - len(mix)
        if need > 0:
            mix.extend([0.0] * need)
        for i, v in enumerate(s):
            mix[first + i] += v

    t = 0.2
    for material in order:
        for path in banks[material]:
            place(t, path)
            t += 0.5
        t += 0.6
    for path in shots:
        place(t, path)
        t += 1.2
    for material in order[:3]:
        for k in range(8):
            place(t, banks[material][k % len(banks[material])])
            t += 0.15
        t += 0.8
    peak = max(abs(v) for v in mix)
    frames = b"".join(struct.pack("<h", int(max(-32768, min(32767, round(v * 32767))))) for v in mix)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)
    print(f"wrote {out} ({len(mix) / rate:.1f} s, peak {peak:.2f}); order: {', '.join(order)}")


if __name__ == "__main__":
    main()
