"""Stereo extrinsics from two board videos (auto-synced).

The two extrinsics videos aren't time-synced, so we:
  1. detect the board in both videos over time,
  2. estimate the time offset by cross-correlating the "board visible" signals,
  3. pair frames seen by BOTH cameras at the same instant (board held still, so
     small timing error is harmless),
  4. run cv2.stereoCalibrate with the FIXED per-camera intrinsics -> R, t.

Usage (from code/):
    .venv\\Scripts\\python.exe scripts\\run_stereo.py ^
        data\\cam1_extrinsics.MOV data\\cam2_extrinsics.MOV ^
        --board calibration\\board_measured_large.json
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, Intrinsics, make_detector, detect_board  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.paths import CALIB_ACTIVE  # noqa: E402


def scan(video, spec, sample_fps=20.0, min_corners=8):
    """Return (fps, duration, list of (t, corners, ids)) for detected frames."""
    detector = make_detector(spec)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps / sample_fps)))
    out, idx = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            c, i = detect_board(g, detector)
            if i is not None and len(i) >= min_corners:
                out.append((idx / fps, c.reshape(-1, 2), i.flatten()))
        idx += 1
    cap.release()
    return fps, total / fps, out


def estimate_offset(det1, det2, dur, bin_s=0.1, max_shift_s=15.0):
    """Cross-correlate board-visible signals -> time offset (t2 = t1 + offset)."""
    n = int(dur / bin_s) + 1
    s1, s2 = np.zeros(n), np.zeros(n)
    for t, _, _ in det1:
        s1[min(int(t / bin_s), n - 1)] = 1
    for t, _, _ in det2:
        s2[min(int(t / bin_s), n - 1)] = 1
    best, best_shift = -1, 0
    for shift in range(-int(max_shift_s / bin_s), int(max_shift_s / bin_s) + 1):
        ov = np.sum(s1 * np.roll(s2, shift))
        if ov > best:
            best, best_shift = ov, shift
    return -best_shift * bin_s  # offset so that t1 ~ t2 + offset


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video1")
    ap.add_argument("video2")
    ap.add_argument("--board", default=str(CALIB_ACTIVE / "board_measured_large.json"))
    ap.add_argument("--intr1", default=str(CALIB_ACTIVE / "intrinsics_cam1.npz"))
    ap.add_argument("--intr2", default=str(CALIB_ACTIVE / "intrinsics_cam2.npz"))
    ap.add_argument("--max-pairs", type=int, default=25)
    ap.add_argument("--tol", type=float, default=0.08, help="pair time tolerance (s)")
    args = ap.parse_args()

    spec = BoardSpec.from_measured_json(args.board)
    board = spec.board()
    board_obj = board.getChessboardCorners()          # (Ncorners, 3)
    intr1, intr2 = Intrinsics.load(args.intr1), Intrinsics.load(args.intr2)

    print("Scanning cam1..."); fps1, dur1, d1 = scan(args.video1, spec)
    print(f"  {len(d1)} detected samples")
    print("Scanning cam2..."); fps2, dur2, d2 = scan(args.video2, spec)
    print(f"  {len(d2)} detected samples")

    offset = estimate_offset(d1, d2, max(dur1, dur2))
    print(f"Estimated time offset: cam1 = cam2 + {offset:.2f} s")

    # Group each camera's detections into STILL holds (board barely moving).
    # Only holds give trustworthy correspondences: during a still hold the exact
    # sync is irrelevant because both cameras see the identical pose.
    def make_holds(dets, move_px=25.0, max_gap_s=0.2, min_dur_s=0.4):
        holds, run = [], []
        for t, c, i in dets:
            ctr = c.mean(axis=0)
            if run and (t - run[-1][0] > max_gap_s or
                        np.linalg.norm(ctr - run[-1][3]) > move_px):
                if run[-1][0] - run[0][0] >= min_dur_s:
                    holds.append(run)
                run = []
            run.append((t, c, i, ctr))
        if run and run[-1][0] - run[0][0] >= min_dur_s:
            holds.append(run)
        # representative = detection with the most corners in the run
        reps = [max(h, key=lambda x: len(x[2])) for h in holds]
        return reps  # list of (t, corners, ids, centroid)

    h1, h2 = make_holds(d1), make_holds(d2)
    print(f"Still holds: cam1={len(h1)}, cam2={len(h2)}")

    # Match cam1 holds to cam2 holds by aligned time (holds are ~seconds, so a
    # generous tolerance is fine).
    t2h = np.array([h[0] for h in h2]) if h2 else np.array([])
    pairs, used = [], set()
    for t1, c1, i1, _ in h1:
        if len(t2h) == 0:
            break
        j = int(np.argmin(np.abs(t2h - (t1 - offset))))
        if j not in used and abs(t2h[j] - (t1 - offset)) <= 0.6:
            used.add(j)
            pairs.append((c1, i1, h2[j][1], h2[j][2], c1.mean(axis=0)))

    print(f"Matched simultaneous still holds: {len(pairs)}")
    if len(pairs) < 4:
        raise SystemExit("Too few shared views (<4). Need more poses seen by BOTH "
                         "cameras at once.")

    # For each pair, solve the board pose in each camera independently (PnP) and
    # derive the cam2<-cam1 relative pose. Correct pairs (board truly still in
    # both) agree; mismatched pairs (paired across board motion) are outliers.
    def rel_pose(c1, i1, c2, i2):
        shared = np.intersect1d(i1, i2)
        if len(shared) < 8:
            return None
        m1 = {int(v): c1[k] for k, v in enumerate(i1)}
        m2 = {int(v): c2[k] for k, v in enumerate(i2)}
        objp = np.array([board_obj[int(s)] for s in shared], np.float32)
        p1 = np.array([m1[int(s)] for s in shared], np.float32)
        p2 = np.array([m2[int(s)] for s in shared], np.float32)
        ok1, r1, t1 = cv2.solvePnP(objp, p1, intr1.camera_matrix, intr1.dist_coeffs)
        ok2, r2, t2 = cv2.solvePnP(objp, p2, intr2.camera_matrix, intr2.dist_coeffs)
        if not (ok1 and ok2):
            return None
        R1, _ = cv2.Rodrigues(r1)
        R2, _ = cv2.Rodrigues(r2)
        R_rel = R2 @ R1.T
        t_rel = (t2 - R_rel @ t1).ravel()
        return objp, p1, p2, R_rel, t_rel

    cand = [rp for p in pairs if (rp := rel_pose(p[0], p[1], p[2], p[3]))]
    baselines = np.array([np.linalg.norm(c[4]) for c in cand])
    med = float(np.median(baselines))
    print(f"Per-pair baseline estimates: median {med:.3f} m, "
          f"spread {baselines.min():.2f}-{baselines.max():.2f} m ({len(cand)} pairs)")

    # Keep pairs whose baseline agrees with the median (geometric inliers).
    inl = [c for c, b in zip(cand, baselines) if abs(b - med) <= 0.10 * med]
    print(f"Geometric inliers: {len(inl)}")
    if len(inl) < 4:
        raise SystemExit("Too few consistent pairs — board motion/sync issues.")

    obj_pts = [c[0] for c in inl[:args.max_pairs]]
    img1 = [c[1] for c in inl[:args.max_pairs]]
    img2 = [c[2] for c in inl[:args.max_pairs]]
    print(f"Correspondence sets: {len(obj_pts)}")
    rms, _, _, _, _, R, T, _, _ = cv2.stereoCalibrate(
        obj_pts, img1, img2,
        intr1.camera_matrix, intr1.dist_coeffs,
        intr2.camera_matrix, intr2.dist_coeffs,
        intr1.image_size, flags=cv2.CALIB_FIX_INTRINSIC)

    extr = StereoExtrinsics(R, T, float(rms), len(obj_pts))
    out = CALIB_ACTIVE / "stereo_extrinsics.npz"
    extr.save(out)
    print(f"\n=== STEREO RESULT ===")
    print(f"  stereo RMS reprojection error = {rms:.4f} px")
    print(f"  baseline (camera separation)  = {extr.baseline_m():.3f} m")
    print(f"  saved -> {out}")


if __name__ == "__main__":
    main()
