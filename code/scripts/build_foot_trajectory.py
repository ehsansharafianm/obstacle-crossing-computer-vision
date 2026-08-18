"""Build a 3D foot-marker trajectory from a two-marker pilot (green toe + red heel).

Distinct colours → clean cross-camera correspondence (no ambiguity). The shoe is
rigid, so the toe–heel distance must stay constant: we use that to sync the two
cameras (offset that minimises distance variation) and to gauge accuracy during
real foot motion. Output: per-frame 3D of both markers + the toe-height signal.
"""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.reconstruct import triangulate_stereo  # noqa: E402
from occ.tracking import detect_foot  # noqa: E402
from occ.filtering import clean_trajectory  # noqa: E402
from occ.worldframe import WorldTransform  # noqa: E402


def track_foot(video):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    ts, G, R = [], [], []
    lg = lr = None
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        g, r = detect_foot(f)
        ts.append(idx / fps)
        G.append(g if g is not None else (np.nan, np.nan))
        R.append(r if r is not None else (np.nan, np.nan))
        idx += 1
    cap.release()
    return np.array(ts), np.array(G, float), np.array(R, float)


def interp(ts, track, q):
    out = np.full((len(q), 2), np.nan)
    good = ~np.isnan(track[:, 0])
    if good.sum() >= 2:
        for a in range(2):
            out[:, a] = np.interp(q, ts[good], track[good, a], np.nan, np.nan)
    return out


def main():
    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr = StereoExtrinsics.load("calibration/stereo_extrinsics.npz")
    R, T = extr.R, extr.t.reshape(3, 1)

    def tri(p1, p2):
        X = triangulate_stereo(p1.reshape(1, 2), p2.reshape(1, 2),
                               intr1.camera_matrix, intr1.dist_coeffs,
                               intr2.camera_matrix, intr2.dist_coeffs, R, T)
        return X[0]

    print("Tracking cam1..."); ts1, G1, R1 = track_foot("data/cam1_pilot.MOV")
    print("Tracking cam2..."); ts2, G2, R2 = track_foot("data/cam2_pilot.MOV")
    print(f"  cam1 green {100*np.mean(~np.isnan(G1[:,0])):.0f}%  red {100*np.mean(~np.isnan(R1[:,0])):.0f}%  |  "
          f"cam2 green {100*np.mean(~np.isnan(G2[:,0])):.0f}%  red {100*np.mean(~np.isnan(R2[:,0])):.0f}%")

    dur = min(ts1[-1], ts2[-1])
    sample = ts1[(ts1 > 1) & (ts1 < ts1[-1]-1)][::20]

    def toe_heel_std(off):
        g1 = interp(ts1, G1, sample); r1 = interp(ts1, R1, sample)
        g2 = interp(ts2, G2, sample - off); r2 = interp(ts2, R2, sample - off)
        d = []
        for k in range(len(sample)):
            if np.isnan(np.concatenate([g1[k], r1[k], g2[k], r2[k]])).any():
                continue
            X = tri(g1[k], g2[k]); Y = tri(r1[k], r2[k])
            dd = np.linalg.norm(X - Y) * 1000
            if 40 < dd < 500:
                d.append(dd)
        return (np.std(d), np.mean(d), len(d)) if len(d) >= 12 else (1e9, 0, len(d))

    best = (1e9, 0.0)
    for off in np.arange(-min(dur, 20)+2, min(dur, 20)-2, 0.25):
        s, _, _ = toe_heel_std(off)
        if s < best[0]:
            best = (s, off)
    for off in np.arange(best[1]-0.3, best[1]+0.3, 0.02):
        s, _, _ = toe_heel_std(off)
        if s < best[0]:
            best = (s, off)
    off = best[1]
    _, dmean, ncnt = toe_heel_std(off)
    print(f"Sync (rigid-foot): cam2 + {off:.3f}s = cam1  |  toe-heel {dmean:.1f} mm, std {best[0]:.1f} mm ({ncnt} frames)")

    # full trajectory on cam1 grid (subsample to ~60 Hz)
    grid = ts1[::4]
    g1 = interp(ts1, G1, grid); r1 = interp(ts1, R1, grid)
    g2 = interp(ts2, G2, grid - off); r2 = interp(ts2, R2, grid - off)
    toe = np.full((len(grid), 3), np.nan); heel = np.full((len(grid), 3), np.nan)
    for k in range(len(grid)):
        if not np.isnan(np.concatenate([g1[k], g2[k]])).any(): toe[k] = tri(g1[k], g2[k])
        if not np.isnan(np.concatenate([r1[k], r2[k]])).any(): heel[k] = tri(r1[k], r2[k])

    # Rigid-pair rejection: the shoe is rigid, so a frame whose toe-heel distance
    # deviates far from the median has a mis-triangulated marker -> drop it.
    d = np.linalg.norm(toe - heel, axis=1)
    med = np.nanmedian(d); mad = np.nanmedian(np.abs(d - med)) + 1e-9
    bad = ~np.isnan(d) & (np.abs(d - med) > max(0.03, 5 * mad))   # >30mm or 5*MAD
    toe[bad] = np.nan; heel[bad] = np.nan
    print(f"Rigid-pair filter: kept toe-heel {med*1000:.0f} mm, dropped {int(bad.sum())} outlier frames")

    # World frame (Z = height above floor) if the transform has been computed.
    wt_path = Path("calibration/world_transform.npz")
    if wt_path.exists():
        W = WorldTransform.load(wt_path)
        toe = W.apply(toe); heel = W.apply(heel)
        frame_label = "world frame (Z = height above floor)"
    else:
        frame_label = "camera-1 frame (Z = depth) - no world_transform.npz"

    fps = 1/np.median(np.diff(grid))
    toe_c = clean_trajectory(toe, fps); heel_c = clean_trajectory(heel, fps)
    print(f"Output: {frame_label}")
    nok = np.mean(~np.isnan(toe_c[:, 0]))
    print(f"Foot trajectory: {int(nok*len(grid))}/{len(grid)} frames, toe {nok*100:.0f}% reconstructed")

    Path("results").mkdir(exist_ok=True)
    with open("results/foot_trajectory.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["time_s", "toe_x_mm", "toe_y_mm", "toe_z_mm", "heel_x_mm", "heel_y_mm", "heel_z_mm"])
        for k in range(len(grid)):
            row = [f"{grid[k]:.4f}"]
            for arr in (toe_c[k], heel_c[k]):
                for v in arr*1000: row.append("" if np.isnan(v) else f"{v:.2f}")
            w.writerow(row)

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(11, 8))
    ax[0].plot(grid, toe_c[:, 2]*1000, color="#2E9E4F", lw=1.4, label="toe height")
    ax[0].plot(grid, heel_c[:, 2]*1000, color="#C0392B", lw=1.0, label="heel height")
    ax[0].set_title("Foot marker HEIGHT over time  (vertical = clearance axis)")
    ax[0].set_xlabel("time (s)"); ax[0].set_ylabel("height Z (mm)"); ax[0].legend(fontsize=9)
    thd = np.linalg.norm((toe_c-heel_c), axis=1)*1000
    ax[1].plot(grid, thd, color="#34495E", lw=1.0)
    ax[1].axhline(np.nanmean(thd), color="#888888", ls=":", lw=0.8)
    ax[1].set_title(f"Toe-heel distance (rigid shoe → should be flat).  mean {np.nanmean(thd):.0f} mm, std {np.nanstd(thd):.1f} mm")
    ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("mm")
    fig.tight_layout(); fig.savefig("results/foot_trajectory.png", dpi=110)
    print("Saved results/foot_trajectory.png and results/foot_trajectory.csv")


if __name__ == "__main__":
    main()
