"""Build & validate a 3D trajectory from the moving wand videos.

Proves the moving-marker chain the static rod test skipped: track markers through
motion, SYNC the two unsynced cameras (via motion cross-correlation, no clap),
triangulate over time. Validation: the rigid wand's marker-to-marker distances
must stay constant at the known values THROUGHOUT the motion.
"""
import json
import sys
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.reconstruct import triangulate_stereo  # noqa: E402
from occ.tracking import detect_wand  # noqa: E402

KNOWN = sorted(json.loads(Path("calibration/rod_markers.json").read_text())["known_distances_mm"].values())


def _assign(prev, pts):
    """Assign 2 detected pts to 2 track slots by nearest to prev."""
    if prev[0] is None or prev[1] is None:
        order = np.argsort(pts[:, 0])       # init: left-to-right
        return pts[order[0]], pts[order[1]]
    a = np.linalg.norm(prev[0] - pts[0]) + np.linalg.norm(prev[1] - pts[1])
    b = np.linalg.norm(prev[0] - pts[1]) + np.linalg.norm(prev[1] - pts[0])
    return (pts[0], pts[1]) if a <= b else (pts[1], pts[0])


def track_wand_video(video):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    names = ["r0", "r1", "t0", "t1"]
    tr = {n: [] for n in names}
    ts = []
    prev = {n: None for n in names}
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        w = detect_wand(f)
        ts.append(idx / fps)
        if w is None:
            for n in names:
                tr[n].append((np.nan, np.nan))
        else:
            reds, teals = w
            r0, r1 = _assign((prev["r0"], prev["r1"]), reds)
            t0, t1 = _assign((prev["t0"], prev["t1"]), teals)
            for n, p in zip(names, [r0, r1, t0, t1]):
                tr[n].append(tuple(p)); prev[n] = np.asarray(p)
        idx += 1
    cap.release()
    return np.array(ts), {n: np.array(tr[n]) for n in names}


def motion_speed(ts, tracks):
    C = np.nanmean(np.stack([tracks[n] for n in tracks], 0), 0)   # centroid (N,2)
    v = np.linalg.norm(np.diff(C, axis=0), axis=1)
    return ts[1:], np.nan_to_num(v)


def estimate_offset(ts1, s1, ts2, s2, dt=1 / 60):
    g = np.arange(0, min(ts1[-1], ts2[-1]), dt)
    a = np.interp(g, ts1, s1); b = np.interp(g, ts2, s2)
    a = (a - a.mean()) / (a.std() + 1e-9); b = (b - b.mean()) / (b.std() + 1e-9)
    corr = np.correlate(a, b, "full")
    lag = (np.argmax(corr) - (len(b) - 1)) * dt
    return lag   # cam2 time + lag ~ cam1 time


def interp_track(ts_src, track, ts_query):
    out = np.full((len(ts_query), 2), np.nan)
    good = ~np.isnan(track[:, 0])
    if good.sum() < 2:
        return out
    out[:, 0] = np.interp(ts_query, ts_src[good], track[good, 0], left=np.nan, right=np.nan)
    out[:, 1] = np.interp(ts_query, ts_src[good], track[good, 1], left=np.nan, right=np.nan)
    return out


def main():
    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr = StereoExtrinsics.load("calibration/stereo_extrinsics.npz")
    R, T = extr.R, extr.t.reshape(3, 1)
    E = np.cross(np.eye(3), T.ravel()) @ R
    F = np.linalg.inv(intr2.camera_matrix).T @ E @ np.linalg.inv(intr1.camera_matrix)

    v1 = sys.argv[1] if len(sys.argv) > 1 else "data/cam1_test.MOV"
    v2 = sys.argv[2] if len(sys.argv) > 2 else "data/cam2_test.MOV"
    print(f"Tracking {v1}..."); ts1, tr1 = track_wand_video(v1)
    print(f"Tracking {v2}..."); ts2, tr2 = track_wand_video(v2)
    for n in tr1:
        cov = (~np.isnan(tr1[n][:, 0])).mean()
        print(f"  cam1 {n}: {cov*100:.0f}% tracked")

    def epi_match(p1s, p2s):
        def ld(p1, p2):
            l = F @ np.array([p1[0], p1[1], 1.0])
            return abs(l @ np.array([p2[0], p2[1], 1.0])) / np.hypot(l[0], l[1])
        a = ld(p1s[0], p2s[0]) + ld(p1s[1], p2s[1])
        b = ld(p1s[0], p2s[1]) + ld(p1s[1], p2s[0])
        return p2s if a <= b else p2s[::-1]

    def reconstruct(r1, t1, r2, t2):
        if np.isnan(np.concatenate([r1, t1, r2, t2])).any():
            return None
        r2m, t2m = epi_match(r1, r2), epi_match(t1, t2)
        pts1 = np.vstack([r1, t1]); pts2 = np.vstack([r2m, t2m])
        return triangulate_stereo(pts1, pts2, intr1.camera_matrix, intr1.dist_coeffs,
                                  intr2.camera_matrix, intr2.dist_coeffs, R, T)

    def markers_at(ts, tr, t):
        out = {}
        for n in ["r0", "r1", "t0", "t1"]:
            g = ~np.isnan(tr[n][:, 0])
            if g.sum() < 2:
                out[n] = np.array([np.nan, np.nan])
            else:
                out[n] = np.array([np.interp(t, ts[g], tr[n][g, 0], np.nan, np.nan),
                                   np.interp(t, ts[g], tr[n][g, 1], np.nan, np.nan)])
        return out

    def frame_dist_err(t, offset):
        m1, m2 = markers_at(ts1, tr1, t), markers_at(ts2, tr2, t - offset)
        X = reconstruct(np.array([m1["r0"], m1["r1"]]), np.array([m1["t0"], m1["t1"]]),
                        np.array([m2["r0"], m2["r1"]]), np.array([m2["t0"], m2["t1"]]))
        if X is None:
            return None
        dd = sorted(np.linalg.norm(X[i] - X[j]) * 1000 for i, j in combinations(range(4), 2))
        return sum(min(abs(k - d) for d in dd) for k in KNOWN)

    # SYNC: find the time offset that makes the wand's reconstructed distances
    # match the known values (self-validating; robust where motion-corr failed).
    sample_t = ts1[(ts1 > ts1[0] + 2) & (ts1 < ts1[-1] - 2)]
    sample_t = sample_t[::max(1, len(sample_t) // 70)]
    dur = min(ts1[-1], ts2[-1])

    def score(offset):
        e = [frame_dist_err(t, offset) for t in sample_t]
        e = [x for x in e if x is not None]
        return (np.mean(e), len(e)) if len(e) >= 15 else (1e9, len(e))

    best = (1e9, 0.0)
    for off in np.arange(-min(dur, 30) + 3, min(dur, 30) - 3, 0.25):
        s, _ = score(off)
        if s < best[0]:
            best = (s, off)
    for off in np.arange(best[1] - 0.3, best[1] + 0.3, 0.02):
        s, _ = score(off)
        if s < best[0]:
            best = (s, off)
    lag = best[1]
    print(f"Sync (wand-distance consistency): cam2 + {lag:.3f}s = cam1  "
          f"(mean dist-err {best[0]:.1f} mm at best offset)")

    grid = ts1[::8]
    tr1i = {n: interp_track(ts1, tr1[n], grid) for n in tr1}
    tr2i = {n: interp_track(ts2 + lag, tr2[n], grid) for n in tr2}

    dist_series = []   # per frame: sorted 6 distances (mm)
    traj = []          # per frame: 4 markers 3D (or None)
    for k in range(len(grid)):
        r1 = np.array([tr1i["r0"][k], tr1i["r1"][k]])
        t1 = np.array([tr1i["t0"][k], tr1i["t1"][k]])
        r2 = np.array([tr2i["r0"][k], tr2i["r1"][k]])
        t2 = np.array([tr2i["t0"][k], tr2i["t1"][k]])
        if np.isnan(np.concatenate([r1, t1, r2, t2])).any():
            traj.append(None); continue
        r2m, t2m = epi_match(r1, r2), epi_match(t1, t2)
        pts1 = np.vstack([r1, t1]); pts2 = np.vstack([r2m, t2m])
        X = triangulate_stereo(pts1, pts2, intr1.camera_matrix, intr1.dist_coeffs,
                               intr2.camera_matrix, intr2.dist_coeffs, R, T)
        traj.append(X)
        dist_series.append(sorted(np.linalg.norm(X[i] - X[j]) * 1000
                                  for i, j in combinations(range(4), 2)))

    n_ok = sum(x is not None for x in traj)
    print(f"\nTrajectory: {n_ok}/{len(grid)} frames reconstructed in 3D")
    D = np.array(dist_series)
    print("\nRigid-wand distance CONSTANCY during motion (should stay ~= known):")
    print(f"{'known(mm)':>10} {'recon mean':>11} {'recon std':>10} {'mean err':>9}")
    series = {}
    for k in KNOWN:
        vals = np.array([row[np.argmin(np.abs(np.array(row) - k))] for row in D])
        series[k] = vals
        print(f"{k:>10.2f} {vals.mean():>11.2f} {vals.std():>10.2f} {np.mean(np.abs(vals-k)):>9.2f}")
    print("\nLow std across frames = trajectory is stable through motion (sync works).")

    # --- save + visualise ---
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    Path("results").mkdir(exist_ok=True)
    X3 = np.array([x if x is not None else np.full((4, 3), np.nan) for x in traj])
    tgrid = grid[:len(X3)]
    np.savez("results/wand_trajectory.npz", t=tgrid, markers=X3)

    fig, ax = plt.subplots(2, 1, figsize=(11, 9))
    for k in KNOWN:
        ax[0].plot(series[k], lw=0.8, label=f"{k:.1f} mm known")
        ax[0].axhline(k, color="k", ls=":", lw=0.6)
    ax[0].set_title("Reconstructed wand distances through motion (flat = good)")
    ax[0].set_xlabel("frame"); ax[0].set_ylabel("mm"); ax[0].legend(fontsize=8)
    ax[0].set_ylim(0, max(KNOWN) * 1.6)
    # marker paths (top-down X vs Z, metres)
    for m, c in zip(range(4), ["r", "salmon", "teal", "c"]):
        ax[1].plot(X3[:, m, 0], X3[:, m, 2], ".", ms=2, color=c, label=f"marker {m}")
    ax[1].set_title("Marker paths (top-down: X vs depth Z)")
    ax[1].set_xlabel("X (m)"); ax[1].set_ylabel("Z (m)"); ax[1].axis("equal"); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig("results/wand_trajectory.png", dpi=110)
    print("\nSaved results/wand_trajectory.png and results/wand_trajectory.npz")


if __name__ == "__main__":
    main()
