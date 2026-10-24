"""Cut a footstep (or impact) recording into single-contact one-shots that meet a game's
one-shot rules: one strike, 40 dB down from `--tail` ms on, silent at the end, levelled.

    uv run --with numpy python cut_contacts.py <src.wav> <out dir> <prefix> [--keep N]
        [--loud dB] [--max ms] [--min ms] [--tail ms] [--gap ms] [--from s] [--to s]
        [--whole] [--list]

<src.wav> is 44.1 kHz mono 16-bit (ffmpeg -ac 1 -ar 44100 -c:a pcm_s16le). Contacts are rises
of 6 dB within 10 ms above -24 dB of the file's loudest 5 ms, 35 ms or more apart; contacts
closer than `--gap` (250 ms) are one step: heel and toe. A slice runs from 3 ms before the heel
to 8 ms before the toe (or `--max`, 260 ms), fades 30 ms into that cut, gets 25 ms of silence,
a 30 Hz high-pass, and is levelled to `--loud` dBFS (-18; the RMS of its loudest 20 ms, peak
capped at 0.85). `--whole` keeps crunches and splashes past the toe and only damps them after
30 ms when a later grain would count as a strike. Of the usable slices at least `--min` ms long
(60) the ones nearest the median loudness and spectrum are kept, spread over the recording, as
<prefix>_1.wav ... `--list` prints every candidate and why it failed instead.
Shots: --whole --max 600 --tail 500 --gap 1500 --loud -12.
"""
import sys
import wave
from pathlib import Path

import numpy as np

RATE = 44100
WIN = RATE // 200  # 5 ms
PEAK = 0.85


def load(path):
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768


def save(path, x):
    pcm = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def levels(x):
    n = len(x) // WIN
    out = np.sqrt(np.mean(x[: n * WIN].reshape(n, WIN) ** 2, axis=1))
    if len(x) > n * WIN:
        out = np.append(out, np.sqrt(np.mean(x[n * WIN:] ** 2)))
    return out


def strikes(x, loudest=None):
    rms = levels(x)
    loudest = max(loudest if loudest is not None else rms.max(), 1e-9)
    db = 20 * np.log10(np.maximum(rms / loudest, 1e-9))
    found = []
    for i in range(len(db)):
        before = db[i - 2] if i >= 2 else -200.0
        apart = not found or i - found[-1] > 6
        if db[i] > -24 and db[i] - before > 6 and apart:
            found.append(i)
    return found


def highpass(x, cutoff=30.0):
    a = np.exp(-2 * np.pi * cutoff / RATE)
    y = np.empty_like(x)
    state = 0.0
    for i in range(len(x)):
        state = (1 - a) * x[i] + a * state
        y[i] = x[i] - state
    return y


def fade_out(x, start, end):
    out = x.copy()
    end = min(end, len(out))
    if end > start:
        k = np.arange(end - start)
        out[start:end] *= 0.5 + 0.5 * np.cos(np.pi * k / (end - start))
    out[end:] = 0.0
    return out


def a_weight(freqs):
    f2 = np.maximum(freqs, 1.0) ** 2
    ra = (12194.0**2 * f2**2) / ((f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2))
                                 * (f2 + 12194.0**2))
    return (ra * 10 ** (2.0 / 20)) ** 2


def spectrum(x):
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    return freqs, spec * a_weight(freqs)


def bands(x):
    freqs, spec = spectrum(x)
    total = spec.sum() or 1e-12
    edges = np.geomspace(80, 12000, 17)
    b = np.array([spec[(freqs >= lo) & (freqs < hi)].sum() for lo, hi in zip(edges, edges[1:])])
    padded = np.concatenate([[b[0]], b, [b[-1]]])
    b = 0.25 * padded[:-2] + 0.5 * padded[1:-1] + 0.25 * padded[2:]
    return 10 * np.log10(np.maximum(b / total, 1e-4))


def centroid(x):
    freqs, spec = spectrum(x)
    return float((freqs * spec).sum() / (spec.sum() or 1e-12))


def shape(piece, loud_db, max_s, tail_s, whole):
    piece = highpass(piece)
    peak = np.abs(piece).max()
    above = np.nonzero(np.abs(piece) > peak * 10 ** (-30 / 20))[0]
    start = max(0, int(above[0]) - int(0.003 * RATE)) if len(above) else 0
    piece = piece[start:][: int(max_s * RATE)]
    hits = strikes(piece)
    if not whole and len(hits) > 1:
        cut = hits[1] * WIN - int(0.008 * RATE)
        if cut >= int(0.06 * RATE):
            piece = piece[:cut]
    fade = min(int(0.030 * RATE), int(0.4 * len(piece)))
    piece = fade_out(piece, len(piece) - fade, len(piece))
    piece = np.concatenate([piece, np.zeros(int(0.025 * RATE))])
    if len(piece) > int(tail_s * RATE):
        piece = fade_out(piece, int((tail_s - 0.05) * RATE), int(tail_s * RATE))
        piece = piece[: int(tail_s * RATE) + 1]
    damped = 0.0
    for damping in (0.0, 0.12, 0.08, 0.06, 0.045, 0.035):
        trial = piece.copy()
        if damping:
            t = np.arange(len(trial)) / RATE
            trial *= np.where(t < 0.03, 1.0, np.exp(-(t - 0.03) / damping))
        if len(strikes(trial)) == 1:
            piece, damped = trial, damping
            break
    else:
        return None, "strikes", 0.0
    rms = levels(piece)
    late = rms[int(tail_s * 200):]
    if len(late) and late.max() > rms.max() * 0.01:
        return None, "tail", damped
    window = int(0.020 * RATE)
    loudest = max(np.sqrt(np.mean(piece[i:i + window] ** 2))
                  for i in range(0, max(1, len(piece) - window), WIN))
    gain = min(10 ** (loud_db / 20) / max(loudest, 1e-9), PEAK / max(np.abs(piece).max(), 1e-9))
    piece = piece * gain
    end = piece[-int(0.020 * RATE):]
    if np.sqrt(np.mean(end ** 2)) > np.abs(piece).max() * 0.001:
        return None, "end", damped
    return piece, "ok", damped


def main():
    args = sys.argv[1:]
    src, out, prefix = Path(args[0]), Path(args[1]), args[2]
    opt = lambda name, default: float(args[args.index(name) + 1]) if name in args else default  # noqa: E731
    keep = int(opt("--keep", 5))
    loud_db = opt("--loud", -18.0)
    max_s, min_s = opt("--max", 260.0) / 1000, opt("--min", 60.0) / 1000
    tail_s, gap_s = opt("--tail", 250.0) / 1000, opt("--gap", 250.0) / 1000
    span = (opt("--from", 0.0), opt("--to", 1e9))
    whole = "--whole" in args
    x = load(src)
    contacts = [c * WIN for c in strikes(x, loudest=levels(x).max())
                if span[0] <= c * WIN / RATE <= span[1]]
    steps = []
    for c in contacts:
        if steps and c - steps[-1][0] < int(gap_s * RATE):
            steps[-1].append(c)
        else:
            steps.append([c])
    rows = []
    for k, step in enumerate(steps):
        heel = step[0]
        toe = step[1] if len(step) > 1 and not whole else None
        following = steps[k + 1][0] if k + 1 < len(steps) else len(x)
        end = heel + int(max_s * RATE)
        if toe is not None:
            end = min(end, toe - int(0.008 * RATE))
        end = min(end, following - int(0.010 * RATE), len(x))
        piece = x[max(0, heel - int(0.010 * RATE)):end]
        if len(piece) < int(min_s * RATE):
            rows.append((heel / RATE, -99.0, 0.0, "short", None, 0.0))
            continue
        raw = 20 * np.log10(max(np.sqrt(np.mean(piece[: int(0.05 * RATE)] ** 2)), 1e-9))
        before = x[max(0, heel - int(0.060 * RATE)):max(1, heel - int(0.015 * RATE))]
        snr = raw - 20 * np.log10(max(np.sqrt(np.mean(before ** 2)), 1e-9))
        shaped, why, damped = shape(piece, loud_db, max_s, tail_s, whole)
        rows.append((heel / RATE, raw, snr, why, shaped, damped))
    ok = [r for r in rows if r[3] == "ok"]
    if "--list" in args:
        for at, raw, snr, why, shaped, damped in rows:
            extra = f"  centroid {centroid(shaped):5.0f} Hz" if shaped is not None else ""
            note = f"  damped {damped:.3f}" if damped else ""
            print(f"{at:7.2f} s  raw {raw:6.1f} dB  floor {snr:5.1f} dB below  {why:7}{note}{extra}")
        print(f"{len(ok)} of {len(rows)} usable")
        return
    if not ok:
        sys.exit(f"{prefix}: nothing usable of {len(rows)} steps")
    median_raw = float(np.median([r[1] for r in ok]))
    pool = ok
    for within, floor in ((8.0, 10.0), (12.0, 6.0), (18.0, 0.0)):
        narrowed = [r for r in ok if abs(r[1] - median_raw) <= within and r[2] >= floor]
        if len(narrowed) >= keep + 2:
            pool = narrowed
            break
    vectors = np.array([bands(r[4]) for r in pool])
    median = np.median(vectors, axis=0)
    ranked = sorted(zip(pool, vectors), key=lambda rv: np.linalg.norm(rv[1] - median))
    nearest = sorted((rv[0] for rv in ranked[: keep + 2]), key=lambda r: r[0])
    picks = sorted({int(round(i)) for i in np.linspace(0, len(nearest) - 1, min(keep, len(nearest)))})
    out.mkdir(parents=True, exist_ok=True)
    for n, i in enumerate(picks, 1):
        at, raw, snr, _, shaped, damped = nearest[i]
        save(out / f"{prefix}_{n}.wav", shaped)
        note = f", damped {damped:.3f}" if damped else ""
        print(f"{prefix}_{n}: {at:6.2f} s in, {len(shaped) / RATE:.2f} s, "
              f"centroid {centroid(shaped):.0f} Hz{note}")
    print(f"{prefix}: {len(picks)} of {len(ok)} usable slices kept ({len(rows)} steps)")


if __name__ == "__main__":
    main()
