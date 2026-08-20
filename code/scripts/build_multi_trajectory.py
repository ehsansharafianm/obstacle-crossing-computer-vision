"""Build 3D trajectories for the 6-marker study set: two feet (left & right,
each toe+heel) plus two static ground markers. Adapts build_foot_trajectory to
several markers. Reads sessions/<id>/cam1.* + cam2.*, writes the CSV + plot there.

Usage (from code/):  python scripts/build_multi_trajectory.py 7
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
from occ.tracking import detect_two_feet_ground  # noqa: E402
from occ.filtering import clean_trajectory  # noqa: E402
from occ.worldframe import WorldTransform  # noqa: E402
from occ.audiosync import clap_offset  # noqa: E402

EXP_ROOT = Path("sessions")
VIDEO_EXTS = (".MOV", ".mov", ".MP4", ".mp4", ".avi", ".AVI")
FEET = ["L_toe", "L_heel", "R_toe", "R_heel"]
PAIRS = [("L_toe", "L_heel"), ("R_toe", "R_heel")]
COLORS = {"L_toe": "#7C3AED", "L_heel": "#22A559", "R_toe": "#D6336C", "R_heel": "#1098AD"}


def find_cam_video(folder, cam):
    hits = sorted(p for p in folder.glob(f"{cam}*") if p.is_file())
    for ext in VIDEO_EXTS:
        for p in hits:
            if p.suffix == ext:
                return p
    return hits[0] if hits else None


def track(video):
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    ts, F, G = [], {k: [] for k in FEET}, []
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        d = detect_two_feet_ground(f)
        ts.append(idx / fps)
        for k in FEET:
            F[k].append(d[k] if d[k] is not None else (np.nan, np.nan))
        G.append(d["ground"])
        idx += 1
    cap.release()
    return np.array(ts), {k: np.array(F[k], float) for k in FEET}, G


def interp(ts, track, q, max_gap=0.05):
    out = np.full((len(q), 2), np.nan)
    good = ~np.isnan(track[:, 0])
    if good.sum() >= 2:
        tg = ts[good]
        for a in range(2):
            out[:, a] = np.interp(q, tg, track[good, a], np.nan, np.nan)
        j = np.clip(np.searchsorted(tg, q), 1, len(tg) - 1)
        out[np.minimum(q - tg[j - 1], tg[j] - q) > max_gap] = np.nan
    return out


def two_means(pts, iters=15):
    """Split points into 2 clusters (the two ground markers). Returns 2 centroids."""
    pts = np.asarray(pts, float)
    c = np.array([pts[np.argmin(pts[:, 0])], pts[np.argmax(pts[:, 0])]])
    for _ in range(iters):
        lab = np.argmin(((pts[:, None, :] - c[None]) ** 2).sum(-1), axis=1)
        for k in (0, 1):
            if (lab == k).any():
                c[k] = pts[lab == k].mean(0)
    return c


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: build_multi_trajectory.py <test id>")
    raw = sys.argv[1]
    tid = f"test{int(raw):02d}" if str(raw).isdigit() else raw
    folder = EXP_ROOT / tid
    folder.mkdir(parents=True, exist_ok=True)
    cam1 = find_cam_video(folder, "cam1")
    cam2 = find_cam_video(folder, "cam2")
    if cam1 is None or cam2 is None:
        raise SystemExit(f"[{tid}] need cam1/cam2 clips in {folder.resolve()}")

    log = [f"Test: {tid}", ""]

    def say(m=""):
        print(m); log.append(m)

    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr = StereoExtrinsics.load("calibration/stereo_extrinsics.npz")
    R, T = extr.R, extr.t.reshape(3, 1)

    def tri(p1, p2):
        X = triangulate_stereo(p1.reshape(1, 2), p2.reshape(1, 2),
                               intr1.camera_matrix, intr1.dist_coeffs,
                               intr2.camera_matrix, intr2.dist_coeffs, R, T)
        return X[0]

    say(f"[{tid}] tracking {cam1.name} ..."); ts1, F1, G1 = track(cam1)
    say(f"[{tid}] tracking {cam2.name} ..."); ts2, F2, G2 = track(cam2)
    for k in FEET:
        say(f"  {k:7s} cam1 {100*np.mean(~np.isnan(F1[k][:,0])):.0f}%  "
            f"cam2 {100*np.mean(~np.isnan(F2[k][:,0])):.0f}%")

    off, conf = clap_offset(cam1, cam2)
    say(f"Sync: cam2 + {off:.3f}s = cam1  (conf {conf:.0f})")

    W_path = Path("calibration/world_transform.npz")
    W = WorldTransform.load(W_path) if W_path.exists() else None

    grid = ts1[::4]
    world = {}
    for k in FEET:
        a = interp(ts1, F1[k], grid); b = interp(ts2, F2[k], grid - off)
        X = np.full((len(grid), 3), np.nan)
        for i in range(len(grid)):
            if not np.isnan(np.concatenate([a[i], b[i]])).any():
                X[i] = tri(a[i], b[i])
        world[k] = W.apply(X) if W is not None else X

    # per-foot rigid-pair filter + plausibility gate
    for toe, heel in PAIRS:
        d = np.linalg.norm(world[toe] - world[heel], axis=1)
        med = np.nanmedian(d); mad = np.nanmedian(np.abs(d - med)) + 1e-9
        bad = ~np.isnan(d) & (np.abs(d - med) > max(0.04, 4 * mad))
        world[toe][bad] = np.nan; world[heel][bad] = np.nan
        say(f"  {toe[0]} foot: toe-heel {med*1000:.0f} mm, dropped {int(bad.sum())} outliers")
    for k in FEET:
        Z = world[k][:, 2]
        bad = ~np.isnan(Z) & ((Z < -0.10) | (Z > 1.5) |
                              (np.abs(world[k][:, 0]) > 3) | (np.abs(world[k][:, 1]) > 3))
        world[k][bad] = np.nan

    # --- Ground markers: two static reds -> 2 fixed 3D points -----------------
    ground_w = None
    g1 = [p for fr in G1 for p in fr]; g2 = [p for fr in G2 for p in fr]
    if len(g1) >= 4 and len(g2) >= 4:
        c1 = two_means(g1); c2 = two_means(g2)
        best = None
        for perm in ([0, 1], [1, 0]):
            pts = np.array([tri(c1[i], c2[perm[i]]) for i in range(2)])
            ptsw = W.apply(pts) if W is not None else pts
            zerr = np.abs(ptsw[:, 2]).sum()          # both should sit on the floor (Z~0)
            if best is None or zerr < best[0]:
                best = (zerr, ptsw)
        ground_w = best[1]
        say(f"Ground markers (world, mm): "
            + " | ".join(f"({p[0]*1000:.0f},{p[1]*1000:.0f},{p[2]*1000:.0f})" for p in ground_w))

    fps = 1 / np.median(np.diff(grid))
    for k in FEET:
        world[k] = clean_trajectory(world[k], fps)
    frame_label = "world frame (Z = height above floor)" if W is not None else "camera-1 frame"
    say(f"Output: {frame_label}")
    for k in FEET:
        say(f"  {k:7s} {100*np.mean(~np.isnan(world[k][:,0])):.0f}% reconstructed")

    # --- CSV ------------------------------------------------------------------
    csv_path = folder / f"{tid}_trajectory.csv"
    hdr = ["time_s"] + [f"{k}_{a}_mm" for k in FEET for a in "xyz"]
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f); w.writerow(hdr)
        for i in range(len(grid)):
            row = [f"{grid[i]:.4f}"]
            for k in FEET:
                for v in world[k][i] * 1000:
                    row.append("" if np.isnan(v) else f"{v:.2f}")
            w.writerow(row)
    if ground_w is not None:
        with open(folder / f"{tid}_ground.csv", "w", newline="") as f:
            w = csv.writer(f); w.writerow(["marker", "x_mm", "y_mm", "z_mm"])
            for i, p in enumerate(ground_w):
                w.writerow([f"ground{i+1}"] + [f"{v*1000:.2f}" for v in p])

    # --- Plot -----------------------------------------------------------------
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(11, 8))
    for k in FEET:
        ax[0].plot(grid, world[k][:, 2] * 1000, color=COLORS[k], lw=1.3, label=k)
    ax[0].set_title(f"{tid}: marker HEIGHT over time  (both feet)")
    ax[0].set_xlabel("time (s)"); ax[0].set_ylabel("height Z (mm)"); ax[0].legend(fontsize=8, ncol=4)
    for toe, heel in PAIRS:
        d = np.linalg.norm(world[toe] - world[heel], axis=1) * 1000
        ax[1].plot(grid, d, lw=1.0, label=f"{toe[0]} foot toe-heel  (std {np.nanstd(d):.0f} mm)")
    ax[1].set_title("Toe-heel distance per foot (rigid shoe -> flat)")
    ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("mm"); ax[1].legend(fontsize=9)
    fig.tight_layout(); fig.savefig(folder / f"{tid}_trajectory.png", dpi=110)

    say(f"\nSaved {csv_path.name}, {tid}_trajectory.png"
        + (f", {tid}_ground.csv" if ground_w is not None else ""))
    (folder / f"{tid}_run.txt").write_text("\n".join(log) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
