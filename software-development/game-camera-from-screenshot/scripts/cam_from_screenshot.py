"""Recover a game camera (FOV, pitch, roll, yaw, distance) from ONE screenshot via vanishing points.

  python cam_from_screenshot.py detect IMG [--minlen 45]
      -> segs.json + crop_{tl,tr,bl,br}.png with numbered LSD segments (look at them!)
  python cam_from_screenshot.py fit IMG --v 31,22,4,... (--b 3,9,12,... | --b-range 29:40)
          [--b-exclude 171,180] [--grid 2.0]
      -> f, vFOV/hFOV, pitch, roll, yaw-vs-axis, bootstrap 90% CI, overlay_grid.png, fit.json
  python cam_from_screenshot.py scale IMG --obj u,v_foot,v_head,height_m [--obj ...]
      -> camera height, focus distance, ground footprint, ortho half-size (uses fit.json)

V = world-vertical edges (posts, columns, hanging ropes, drum silhouettes).
B = one horizontal world axis (railings, curbs, walls) - pick edges on BOTH sides of the frame.
Assumes square pixels + principal point at image centre; roll is reported so you can check it.
"""
import argparse
import json

import cv2
import numpy as np

S = 1000.0


def detect(a):
    img = cv2.imread(a.img)
    gray = cv2.createCLAHE(3.0, (8, 8)).apply(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    raw = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gray)[0].reshape(-1, 4)
    segs = []
    for x1, y1, x2, y2 in raw:
        L = float(np.hypot(x2 - x1, y2 - y1))
        if L < a.minlen:
            continue
        if y2 > y1:
            x1, y1, x2, y2 = x2, y2, x1, y1
        segs.append(dict(x1=float(x1), y1=float(y1), x2=float(x2), y2=float(y2), L=L,
                         ang=float(np.degrees(np.arctan2(-(y2 - y1), x2 - x1)))))
    json.dump(segs, open("segs.json", "w"))
    vis = cv2.convertScaleAbs(img, alpha=1.6, beta=10)
    for i, s in enumerate(segs):
        an = s["ang"]
        col = (0, 0, 255) if 75 <= an <= 105 else (0, 255, 0) if an < 75 else (255, 160, 0)
        p1, p2 = (int(s["x1"]), int(s["y1"])), (int(s["x2"]), int(s["y2"]))
        cv2.line(vis, p1, p2, col, 1, cv2.LINE_AA)
        cv2.putText(vis, str(i), ((p1[0] + p2[0]) // 2 + 3, (p1[1] + p2[1]) // 2 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    h, w = img.shape[:2]
    for n, (x0, y0) in {"tl": (0, 0), "tr": (w // 2, 0), "bl": (0, h // 2), "br": (w // 2, h // 2)}.items():
        cv2.imwrite(f"crop_{n}.png", vis[y0:y0 + h // 2, x0:x0 + w // 2])
    for i, s in enumerate(segs):
        print(f"{i:4d} ({s['x1']:7.1f},{s['y1']:6.1f})->({s['x2']:7.1f},{s['y2']:6.1f}) L={s['L']:6.1f} ang={s['ang']:6.2f}")
    print(f"{len(segs)} segments >= {a.minlen}px -> segs.json, crop_*.png")


class Fit:
    def __init__(self, segs, w, h):
        self.segs, self.cx, self.cy = segs, w / 2, h / 2

    def hline(self, i):
        s = self.segs[i]
        p1 = np.array([(s["x1"] - self.cx) / S, (s["y1"] - self.cy) / S, 1.0])
        p2 = np.array([(s["x2"] - self.cx) / S, (s["y2"] - self.cy) / S, 1.0])
        l = np.cross(p1, p2)
        return l / np.linalg.norm(l[:2])

    def vp(self, ids):
        A = np.array([self.hline(i) for i in ids]) * np.sqrt([self.segs[i]["L"] for i in ids])[:, None]
        v = np.linalg.svd(A)[2][-1]
        return v / np.linalg.norm(v)

    def err(self, i, v):
        s = self.segs[i]
        m = np.array([((s["x1"] + s["x2"]) / 2 - self.cx) / S, ((s["y1"] + s["y2"]) / 2 - self.cy) / S])
        d = np.array([s["x2"] - s["x1"], s["y2"] - s["y1"]])
        r = v[:2] / v[2] - m if abs(v[2]) > 1e-9 else v[:2]
        return np.degrees(np.arccos(min(1.0, abs(d @ r) / np.linalg.norm(d) / np.linalg.norm(r))))

    def ransac(self, ids, thr, iters=4000):
        rng, best = np.random.default_rng(0), (0, ids)
        for _ in range(iters):
            a, b = rng.choice(ids, 2, replace=False)
            v = np.cross(self.hline(a), self.hline(b))
            if np.linalg.norm(v) < 1e-12:
                continue
            inl = [i for i in ids if self.err(i, v / np.linalg.norm(v)) < thr]
            sc = sum(self.segs[i]["L"] for i in inl)
            if sc > best[0]:
                best = (sc, inl)
        return self.vp(best[1]), best[1]

    def px(self, v):
        return np.array([v[0] / v[2] * S + self.cx, v[1] / v[2] * S + self.cy])

    def solve(self, vz, vb):
        z, b = self.px(vz) - [self.cx, self.cy], self.px(vb) - [self.cx, self.cy]
        f = np.sqrt(-(z @ b))
        roll = np.degrees(np.arctan2(-z[0], z[1]))
        pitch = np.degrees(np.arctan2(f, np.linalg.norm(z)))
        c, s_ = np.cos(np.radians(roll)), np.sin(np.radians(roll))
        yaw = np.degrees(np.arctan((c * b[0] + s_ * b[1]) * np.cos(np.radians(pitch)) / f))
        return f, pitch, roll, yaw


def fit(a):
    img = cv2.imread(a.img)
    h, w = img.shape[:2]
    segs = json.load(open("segs.json"))
    F = Fit(segs, w, h)
    vids = [int(x) for x in a.v.split(",")]
    if a.b:
        bids = [int(x) for x in a.b.split(",")]
    else:
        lo, hi = map(float, a.b_range.split(":"))
        excl = {int(x) for x in a.b_exclude.split(",")} if a.b_exclude else set()
        bids = [i for i, s in enumerate(segs) if lo <= s["ang"] <= hi and i not in excl]
    vz, vin = F.ransac(vids, 0.8)
    vb, bin_ = F.ransac(bids, 0.5)
    f, pitch, roll, yaw = F.solve(vz, vb)
    print(f"V inliers {len(vin)}/{len(vids)}  B inliers {len(bin_)}/{len(bids)}")
    print(f"vertical VP {F.px(vz).round(1)}  axis VP {F.px(vb).round(1)}")
    print(f"f={f:.0f}px  vFOV={2 * np.degrees(np.arctan(h / 2 / f)):.2f}  hFOV={2 * np.degrees(np.arctan(w / 2 / f)):.2f}"
          f"  pitch={pitch:.2f}  roll={roll:.2f}  yaw-vs-axis={yaw:.2f}")
    rng, res = np.random.default_rng(1), []
    for _ in range(1000):
        r = F.solve(F.vp(list(rng.choice(vin, len(vin)))), F.vp(list(rng.choice(bin_, len(bin_)))))
        if np.all(np.isfinite(r)):
            res.append(r)
    res = np.array(res)
    for n, col in [("vFOV", 2 * np.degrees(np.arctan(h / 2 / res[:, 0]))), ("pitch", res[:, 1]),
                   ("roll", res[:, 2]), ("yaw", res[:, 3])]:
        lo, md, hi = np.percentile(col, [5, 50, 95])
        print(f"  {n:5s} median {md:7.2f}  90% CI [{lo:7.2f}, {hi:7.2f}]")
    # overlay: ground grid aligned to the axis + vertical fan, camera height 1 (directions only)
    t, ya = np.radians(pitch), np.radians(yaw)
    Fw, Rw, Dw = np.array([0, np.cos(t), -np.sin(t)]), np.array([1.0, 0, 0]), -np.array([0, np.sin(t), np.cos(t)])
    C = np.array([0, 0, 1.0])
    proj = lambda P: (np.array([w / 2 + f * ((P - C) @ Rw) / ((P - C) @ Fw),
                                h / 2 + f * ((P - C) @ Dw) / ((P - C) @ Fw)]), (P - C) @ Fw)
    ub, uc = np.array([np.sin(ya), np.cos(ya), 0]), np.array([np.cos(ya), -np.sin(ya), 0])
    vis = cv2.convertScaleAbs(img, alpha=1.5, beta=10)
    for k in range(-40, 41):
        for o, d, col in ((k * a.grid / 30 * uc, ub, (0, 255, 0)), (k * a.grid / 30 * ub, uc, (255, 200, 0))):
            pts = [proj(o + s * d) for s in np.linspace(-6, 6, 200)]
            pts = [p for p, z in pts if z > 0 and abs(p).max() < 4 * w]
            for p, q in zip(pts[:-1], pts[1:]):
                cv2.line(vis, tuple(np.int32(p)), tuple(np.int32(q)), col, 1, cv2.LINE_AA)
    pz = F.px(vz)
    for x in range(0, w + 1, w // 12):
        cv2.line(vis, (x, 0), tuple(np.int32(np.array([x, 0]) + 0.35 * (pz - [x, 0]))), (0, 0, 255), 1, cv2.LINE_AA)
    cv2.imwrite("overlay_grid.png", vis)
    json.dump(dict(f=f, pitch=pitch, roll=roll, yaw=yaw, vz=F.px(vz).tolist(), vb=F.px(vb).tolist(),
                   vin=[int(i) for i in vin], bin=[int(i) for i in bin_]), open("fit.json", "w"), indent=1)
    print("wrote overlay_grid.png, fit.json")


def scale(a):
    """Camera height/distance from objects of known height standing on the ground (needs fit.json)."""
    img = cv2.imread(a.img)
    h, w = img.shape[:2]
    fd = json.load(open("fit.json"))
    f, pitch = fd["f"], fd["pitch"]
    t = np.radians(pitch)
    Fw, Rw, Dw = np.array([0, np.cos(t), -np.sin(t)]), np.array([1.0, 0, 0]), -np.array([0, np.sin(t), np.cos(t)])
    C = np.array([0, 0, 1.0])  # unit camera height; real height = known size / ratio

    def ground(u, v):
        d = Fw + (u - w / 2) / f * Rw + (v - h / 2) / f * Dw
        return C + (-1.0 / d[2]) * d

    def vproj(P):
        q = P - C
        return h / 2 + f * (q @ Dw) / (q @ Fw)

    Hs = []
    for o in a.obj:
        u, vf, vh, hm = map(float, o.split(","))
        P, lo, hi = ground(u, vf), 0.0, 0.999
        for _ in range(80):
            r = (lo + hi) / 2
            lo, hi = (r, hi) if vproj(P + [0, 0, r]) > vh else (lo, r)
        Hs.append(hm / r)
        print(f"object at x={u:.0f}: {vf - vh:.0f}px tall, real {hm} m -> camera height {hm / r:6.1f} m")
    Hc = float(np.median(Hs))
    D = Hc / np.sin(t)
    g = {k: ground(*uv) * Hc for k, uv in {"TL": (0, 0), "TR": (w, 0), "BL": (0, h), "BR": (w, h)}.items()}
    print(f"\nmedian camera height {Hc:.1f} m (spread {min(Hs):.1f}-{max(Hs):.1f})")
    print(f"distance camera->focus point (ground at screen centre) D = {D:.1f} m")
    print(f"visible ground: bottom edge {g['BR'][0] - g['BL'][0]:.1f} m, centre {w * D / f:.1f} m, "
          f"top edge {g['TR'][0] - g['TL'][0]:.1f} m wide; {g['TL'][1] - g['BL'][1]:.1f} m deep")
    print(f"ortho equivalent half-height (Unity orthographicSize) = {h / 2 * D / f:.2f} m")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("detect"); d.add_argument("img"); d.add_argument("--minlen", type=float, default=45)
    f_ = sub.add_parser("fit"); f_.add_argument("img"); f_.add_argument("--v", required=True)
    f_.add_argument("--b"); f_.add_argument("--b-range", default="29:40"); f_.add_argument("--b-exclude", default="")
    f_.add_argument("--grid", type=float, default=2.0)
    s_ = sub.add_parser("scale"); s_.add_argument("img")
    s_.add_argument("--obj", action="append", required=True, help="u_foot,v_foot,v_head,height_m (repeatable)")
    a = ap.parse_args()
    {"detect": detect, "fit": fit, "scale": scale}[a.cmd](a)
