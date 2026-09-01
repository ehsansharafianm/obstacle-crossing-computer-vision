"""Build a 3D foot-marker trajectory from a two-marker pilot (green toe + red heel).

Distinct colours → clean cross-camera correspondence (no ambiguity). The shoe is
rigid, so the toe–heel distance must stay constant: we use that to sync the two
cameras (offset that minimises distance variation) and to gauge accuracy during
real foot motion. Output: per-frame 3D of both markers + the toe-height signal.
"""
import argparse
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
from occ.audiosync import clap_offset  # noqa: E402


from occ.paths import session_videos, session_results, CALIB_ACTIVE  # noqa: E402
VIDEO_EXTS = (".MOV", ".mov", ".MP4", ".mp4", ".avi", ".AVI")


def resolve_test_id(raw):
    """A bare number -> testNN (1 -> test01); anything else used verbatim."""
    s = str(raw).strip()
    if s.isdigit():
        return f"test{int(s):02d}"
    return s


def find_cam_video(folder, cam):
    """Find sessions/<id>/cam1.* (or cam2.*); prefer real video extensions."""
    hits = sorted(p for p in folder.glob(f"{cam}*") if p.is_file())
    for ext in VIDEO_EXTS:
        for p in hits:
            if p.suffix == ext:
                return p
    return hits[0] if hits else None


def track_foot(video):
    video = str(video)
    if not Path(video).exists():
        raise SystemExit(f"Video not found: {video}\n"
                         f"  -> put the file in the test folder as cam1/cam2, "
                         f"or pass --cam1 / --cam2 explicitly.")
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video (bad file/codec): {video}")
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


def interp(ts, track, q, max_gap=0.05):
    """Resample a 2D track onto query times `q`, but DON'T bridge long gaps.

    np.interp would draw a straight line across a multi-second dropout (foot out
    of frame), fabricating data. We keep interpolation only within `max_gap`
    seconds of a real detection; deeper into a gap stays NaN (an honest empty).
    """
    out = np.full((len(q), 2), np.nan)
    good = ~np.isnan(track[:, 0])
    if good.sum() >= 2:
        tg = ts[good]
        for a in range(2):
            out[:, a] = np.interp(q, tg, track[good, a], np.nan, np.nan)
        # null query points more than max_gap from the nearest real sample
        j = np.clip(np.searchsorted(tg, q), 1, len(tg) - 1)
        nearest = np.minimum(q - tg[j - 1], tg[j] - q)
        out[nearest > max_gap] = np.nan
    return out


def main():
    ap = argparse.ArgumentParser(
        description="Foot trajectory -> per-test world-frame CSV + plot.",
        epilog="Example: python scripts/build_foot_trajectory.py test01")
    ap.add_argument("test", help="test id (e.g. test01, or a bare number: 1 -> test01). "
                                 "Reads sessions/<id>/cam1.* + cam2.*, writes outputs there.")
    ap.add_argument("--cam1", default=None, help="override: path to camera-1 video")
    ap.add_argument("--cam2", default=None, help="override: path to camera-2 video")
    args = ap.parse_args()

    # --- Resolve this test's folder + input videos -----------------------------
    test_id = resolve_test_id(args.test)
    video_dir = session_videos(test_id)              # raw cam clips (inputs)
    folder = session_results(test_id)                # generated outputs
    folder.mkdir(parents=True, exist_ok=True)
    cam1 = Path(args.cam1) if args.cam1 else find_cam_video(video_dir, "cam1")
    cam2 = Path(args.cam2) if args.cam2 else find_cam_video(video_dir, "cam2")
    if cam1 is None or cam2 is None:
        raise SystemExit(
            f"\n[{test_id}] needs two videos in:\n"
            f"    {video_dir.resolve()}\n"
            f"  -> copy your two clips into it named cam1 and cam2 "
            f"(e.g. cam1.MOV, cam2.MOV), then re-run:\n"
            f"    python scripts/build_foot_trajectory.py {test_id}\n")

    # Every print also goes to sessions/<id>/<id>_run.txt (per-test record).
    _log_lines = [f"Test: {test_id}", f"cam1: {cam1}", f"cam2: {cam2}", ""]

    def say(msg=""):
        print(msg)
        _log_lines.append(msg)

    say(f"[{test_id}]  cam1={cam1.name}  cam2={cam2.name}")

    intr1 = Intrinsics.load(CALIB_ACTIVE / "intrinsics_cam1.npz")
    intr2 = Intrinsics.load(CALIB_ACTIVE / "intrinsics_cam2.npz")
    extr = StereoExtrinsics.load(CALIB_ACTIVE / "stereo_extrinsics.npz")
    R, T = extr.R, extr.t.reshape(3, 1)

    def tri(p1, p2):
        X = triangulate_stereo(p1.reshape(1, 2), p2.reshape(1, 2),
                               intr1.camera_matrix, intr1.dist_coeffs,
                               intr2.camera_matrix, intr2.dist_coeffs, R, T)
        return X[0]

    say(f"Tracking {cam1.name}..."); ts1, G1, R1 = track_foot(cam1)
    say(f"Tracking {cam2.name}..."); ts2, G2, R2 = track_foot(cam2)
    say(f"  cam1 toe {100*np.mean(~np.isnan(G1[:,0])):.0f}%  heel {100*np.mean(~np.isnan(R1[:,0])):.0f}%  |  "
        f"cam2 toe {100*np.mean(~np.isnan(G2[:,0])):.0f}%  heel {100*np.mean(~np.isnan(R2[:,0])):.0f}%")

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

    # Sync: a shared CLAP in the audio is the reliable anchor (works even when
    # the clap is off-frame). Fall back to the rigid-foot offset sweep only if
    # audio is missing or the clap is weak.
    aoff, conf = clap_offset(cam1, cam2)
    if aoff is not None and conf >= 6.0:
        off = aoff
        sstd, dmean, ncnt = toe_heel_std(off)
        say(f"Sync (audio clap): cam2 + {off:.3f}s = cam1  (conf {conf:.0f})  |  "
            f"toe-heel {dmean:.1f} mm, std {sstd:.1f} mm ({ncnt} frames)")
    else:
        reason = "no audio track" if aoff is None else f"weak clap (conf {conf:.1f})"
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
        say(f"Sync (rigid-foot fallback, {reason}): cam2 + {off:.3f}s = cam1  |  "
            f"toe-heel {dmean:.1f} mm, std {best[0]:.1f} mm ({ncnt} frames)")

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
    say(f"Rigid-pair filter: kept toe-heel {med*1000:.0f} mm, dropped {int(bad.sum())} outlier frames")

    # World frame (Z = height above floor) if the transform has been computed.
    wt_path = CALIB_ACTIVE / "world_transform.npz"
    if wt_path.exists():
        W = WorldTransform.load(wt_path)
        toe = W.apply(toe); heel = W.apply(heel)
        frame_label = "world frame (Z = height above floor)"
        # Physical-plausibility gate: a foot marker can't be well below the floor,
        # metres up, or metres outside the capture zone. Drops gross mis-triangs
        # (e.g. a marker matched to a wrong blob) that the rigid-pair test misses
        # when both markers err together. Units: metres, world frame.
        nbad = 0
        for arr in (toe, heel):
            bad = (~np.isnan(arr[:, 2]) &
                   ((arr[:, 2] < -0.10) | (arr[:, 2] > 1.50) |
                    (np.abs(arr[:, 0]) > 3.0) | (np.abs(arr[:, 1]) > 3.0)))
            arr[bad] = np.nan; nbad += int(bad.sum())
        say(f"Plausibility gate: dropped {nbad} out-of-bounds marker points")
    else:
        frame_label = "camera-1 frame (Z = depth) - no world_transform.npz"

    fps = 1/np.median(np.diff(grid))
    toe_c = clean_trajectory(toe, fps); heel_c = clean_trajectory(heel, fps)
    say(f"Output: {frame_label}")
    nok = np.mean(~np.isnan(toe_c[:, 0]))
    say(f"Foot trajectory: {int(nok*len(grid))}/{len(grid)} frames, toe {nok*100:.0f}% reconstructed")

    csv_path = str(folder / f"{test_id}_trajectory.csv")
    png_path = str(folder / f"{test_id}_trajectory.png")
    with open(csv_path, "w", newline="") as f:
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
    fig.suptitle(f"{test_id}", fontsize=11, y=1.0)
    fig.tight_layout(); fig.savefig(png_path, dpi=110)
    say(f"Saved:\n  {csv_path}\n  {png_path}")

    # Per-test run record: the exact numbers for this test, next to its data.
    log_path = folder / f"{test_id}_run.txt"
    log_path.write_text("\n".join(_log_lines) + "\n", encoding="utf-8")
    print(f"  {log_path}")


if __name__ == "__main__":
    main()
