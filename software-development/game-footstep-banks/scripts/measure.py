"""Measure a folder of one-shot WAVs (16-bit mono): A-weighted spectral centroid, high-frequency
share, decay times, strikes (the one-strike rule), and how distinct the materials are.

    uv run --with numpy python measure.py <folder>

Files named step_<material>_<n>.wav are grouped per material for the summary.
"""
import sys
import wave
from pathlib import Path

import numpy as np


def load(path):
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768.0
    return rate, data


def rms_windows(x, rate, ms=5):
    size = max(1, rate * ms // 1000)
    count = len(x) // size
    return np.sqrt(np.mean(x[: count * size].reshape(count, size) ** 2, axis=1))


def strikes(x, rate):
    """Rises of 6 dB within 10 ms to above -24 dB of the loudest 5 ms, 35 ms or more apart."""
    levels = rms_windows(x, rate)
    loudest = max(levels.max(), 1e-9)
    db = 20 * np.log10(np.maximum(levels / loudest, 1e-9))
    found = []
    for i in range(len(db)):
        before = db[i - 2] if i >= 2 else -200.0
        apart = not found or i - found[-1] > 6
        if db[i] > -24 and db[i] - before > 6 and apart:
            found.append(i)
    return [i * 5 / 1000 for i in found]


def decay_time(x, rate, db_down):
    levels = rms_windows(x, rate)
    loudest = max(levels.max(), 1e-9)
    above = np.nonzero(levels > loudest * 10 ** (db_down / 20))[0]
    return (above[-1] + 1) * 0.005 if len(above) else 0.0


def a_weight(freqs):
    """A-weighting as a power gain: roughly what the ear weighs each frequency."""
    f2 = np.maximum(freqs, 1.0) ** 2
    ra = (12194.0**2 * f2**2) / ((f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2))
                                 * (f2 + 12194.0**2))
    return (ra * 10 ** (2.0 / 20)) ** 2


def features(x, rate):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / rate)
    spec = spec * a_weight(freqs)
    total = spec.sum() or 1e-12
    cumulative = np.cumsum(spec) / total
    edges = np.geomspace(80, 12000, 17)
    bands = np.array([spec[(freqs >= lo) & (freqs < hi)].sum() for lo, hi in zip(edges, edges[1:])])
    padded = np.concatenate([[bands[0]], bands, [bands[-1]]])
    bands = 0.25 * padded[:-2] + 0.5 * padded[1:-1] + 0.25 * padded[2:]
    first50 = x[: rate // 20]
    return dict(
        length=len(x) / rate,
        peak=np.abs(x).max(),
        rms50=20 * np.log10(max(np.sqrt(np.mean(first50**2)), 1e-9)),
        centroid=(freqs * spec).sum() / total,
        rolloff85=freqs[np.searchsorted(cumulative, 0.85)],
        above4k=spec[freqs >= 4000].sum() / total,
        above8k=spec[freqs >= 8000].sum() / total,
        below300=spec[freqs < 300].sum() / total,
        t40=decay_time(x, rate, -40),
        t60=decay_time(x, rate, -60),
        strikes=strikes(x, rate),
        bands=10 * np.log10(np.maximum(bands / total, 1e-4)),
    )


def main():
    folder = Path(sys.argv[1])
    rows = {}
    for path in sorted(folder.glob("*.wav")):
        rate, x = load(path)
        rows[path.stem] = features(x, rate)
    print(f"{'file':22} {'len':>5} {'peak':>5} {'rms50':>6} {'cent':>6} {'r85':>6} {'>4k':>5} "
          f"{'>8k':>5} {'<300':>5} {'t40':>5} {'t60':>5} strikes")
    for name, f in rows.items():
        print(f"{name:22} {f['length']:5.2f} {f['peak']:5.2f} {f['rms50']:6.1f} {f['centroid']:6.0f} "
              f"{f['rolloff85']:6.0f} {f['above4k']:5.2f} {f['above8k']:5.2f} {f['below300']:5.2f} "
              f"{f['t40']:5.2f} {f['t60']:5.2f} {len(f['strikes'])} {f['strikes']}")
    materials = {}
    for name, f in rows.items():
        if name.startswith("step_"):
            materials.setdefault(name.rsplit("_", 1)[0][5:], []).append(f)
    if not materials:
        return
    print(f"\n{'material':10} {'centroid':>8} {'t40':>5} {'rms50':>6} {'within':>7}")
    centres, within_max = {}, 0.0
    for material, fs in sorted(materials.items()):
        vectors = np.array([np.append(f["bands"], 40 * f["t40"]) for f in fs])
        centre = vectors.mean(axis=0)
        centres[material] = centre
        within = max(np.linalg.norm(v - centre) for v in vectors)
        within_max = max(within_max, within)
        print(f"{material:10} {np.mean([f['centroid'] for f in fs]):8.0f} "
              f"{np.mean([f['t40'] for f in fs]):5.2f} {np.mean([f['rms50'] for f in fs]):6.1f} "
              f"{within:7.1f}")
    names = sorted(centres)
    pairs = sorted((np.linalg.norm(centres[a] - centres[b]), a, b)
                   for i, a in enumerate(names) for b in names[i + 1:])
    print(f"\nlargest within-material spread {within_max:.1f}; closest pairs (A-weighted band "
          f"energies in dB plus 40 x t40):")
    for d, a, b in pairs[:6]:
        print(f"  {a}-{b} {d:.1f}")


if __name__ == "__main__":
    main()
