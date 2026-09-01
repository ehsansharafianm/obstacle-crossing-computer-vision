"""Stereo extrinsics by GEOMETRIC (time-free) matching.

Time-based hold matching failed (iPad clocks don't align well). Instead: for a
fixed camera pair there is exactly ONE relative pose (R,T). Each still hold has
a board pose per camera (both planar branches). We RANSAC over all (cam1 hold,
cam2 hold, branch) seeds, count how many holds are mutually consistent with the
implied R,T, and keep the largest consistent set -- no timestamps needed. Then
stereoCalibrate on those matched holds with the fixed intrinsics.

Importable: `solve_extrinsics(cam1_video, cam2_video, out=...)` returns the
StereoExtrinsics and its metrics. Run directly for the legacy default paths.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.paths import CALIB_ACTIVE  # noqa: E402
from run_stereo import scan  # noqa: E402


def make_holds(dets, move_px=25.0, max_gap_s=0.2, min_dur_s=0.4):
    holds, run = [], []
    for t, c, i in dets:
        ctr = c.mean(axis=0)
        if run and (t - run[-1][0] > max_gap_s or np.linalg.norm(ctr - run[-1][3]) > move_px):
            if run[-1][0] - run[0][0] >= min_dur_s:
                holds.append(run)
            run = []
        run.append((t, c, i, ctr))
    if run and run[-1][0] - run[0][0] >= min_dur_s:
        holds.append(run)
    return [max(h, key=lambda x: len(x[2])) for h in holds]


def poses(video, spec, K, dist):
    """Per hold: board pose(s) in camera frame (both planar branches)."""
    _, _, dets = scan(video, spec)
    board_obj = spec.board().getChessboardCorners()
    out = []
    for hi, (_, c, i, _) in enumerate(make_holds(dets)):
        objp = np.array([board_obj[int(v)] for v in i], np.float32)
        n, rv, tv, _ = cv2.solvePnPGeneric(objp, c, K, dist, flags=cv2.SOLVEPNP_IPPE)
        for b in range(n):
            R, _ = cv2.Rodrigues(rv[b])
            out.append({"hold": hi, "R": R, "t": tv[b].ravel(),
                        "corners": c, "ids": i.flatten()})
    return out


def solve_extrinsics(cam1_video, cam2_video,
                     board_json=str(CALIB_ACTIVE / "board_measured_large.json"),
                     intr1_path=str(CALIB_ACTIVE / "intrinsics_cam1.npz"),
                     intr2_path=str(CALIB_ACTIVE / "intrinsics_cam2.npz"),
                     out=str(CALIB_ACTIVE / "stereo_extrinsics.npz"),
                     rot_tol_deg=4.0, t_tol=0.15, max_holds=40, verbose=True):
    """Solve stereo extrinsics from two board-at-poses clips. Returns
    (StereoExtrinsics, rms_px, n_pairs).

    `max_holds` caps the distinct board holds per camera (evenly spread across the
    clip). The consistent-set search is O(N^2 * N) in the number of pose branches,
    so a long clip with hundreds of holds explodes; ~40 holds is far more than the
    ~15-20 needed for a good stereo solve and keeps the search fast."""
    def say(*a):
        if verbose:
            print(*a)

    spec = BoardSpec.from_measured_json(board_json)
    intr1 = Intrinsics.load(intr1_path)
    intr2 = Intrinsics.load(intr2_path)

    def cap_holds(P):
        hs = sorted(set(p["hold"] for p in P))
        if len(hs) <= max_holds:
            return P
        keep = {hs[i] for i in np.linspace(0, len(hs) - 1, max_holds).astype(int)}
        return [p for p in P if p["hold"] in keep]

    say(f"Scanning + PnP cam1 ({cam1_video})...")
    P1 = cap_holds(poses(str(cam1_video), spec, intr1.camera_matrix, intr1.dist_coeffs))
    say(f"Scanning + PnP cam2 ({cam2_video})...")
    P2 = cap_holds(poses(str(cam2_video), spec, intr2.camera_matrix, intr2.dist_coeffs))
    R1 = np.array([p["R"] for p in P1]); t1 = np.array([p["t"] for p in P1]); h1 = np.array([p["hold"] for p in P1])
    R2 = np.array([p["R"] for p in P2]); t2 = np.array([p["t"] for p in P2]); h2 = np.array([p["hold"] for p in P2])
    say(f"cam1 holds={len(set(h1))} ({len(P1)} branches), cam2 holds={len(set(h2))} ({len(P2)} branches)")

    ROT_TOL, T_TOL = np.radians(rot_tol_deg), t_tol

    def consistent_pairs(R, T):
        Rp = np.einsum("ij,njk->nik", R, R1)
        tp = np.einsum("ij,nj->ni", R, t1) + T
        seen1, seen2, pairs, order = set(), set(), [], []
        for a in range(len(R1)):
            M = np.einsum("ij,nij->n", Rp[a], R2)
            ang = np.arccos(np.clip((M - 1) / 2, -1, 1))
            td = np.linalg.norm(tp[a] - t2, axis=1)
            score = ang + td
            j = int(np.argmin(score))
            if ang[j] < ROT_TOL and td[j] < T_TOL:
                order.append((score[j], a, j))
        order.sort()
        for _, a, j in order:                       # one branch per hold, greedy best
            if h1[a] in seen1 or h2[j] in seen2:
                continue
            seen1.add(h1[a]); seen2.add(h2[j]); pairs.append((a, j))
        return pairs

    best_pairs = []
    for a in range(len(R1)):
        for b in range(len(R2)):
            R = R2[b] @ R1[a].T
            T = t2[b] - R @ t1[a]
            pr = consistent_pairs(R, T)
            if len(pr) > len(best_pairs):
                best_pairs = pr
    say(f"Largest geometrically-consistent set: {len(best_pairs)} hold-pairs")

    if len(best_pairs) < 4:
        raise SystemExit("Too few consistent pairs -- re-check the extrinsics clips "
                         "(board must be held STATIC at each pose, seen by both cameras).")

    board_obj = spec.board().getChessboardCorners()
    obj_pts, img1, img2 = [], [], []
    for a, j in best_pairs:
        i1, c1 = P1[a]["ids"], P1[a]["corners"]
        i2, c2 = P2[j]["ids"], P2[j]["corners"]
        shared = np.intersect1d(i1, i2)
        if len(shared) < 8:
            continue
        m1 = {int(v): c1[k] for k, v in enumerate(i1)}
        m2 = {int(v): c2[k] for k, v in enumerate(i2)}
        obj_pts.append(np.array([board_obj[int(s)] for s in shared], np.float32))
        img1.append(np.array([m1[int(s)] for s in shared], np.float32))
        img2.append(np.array([m2[int(s)] for s in shared], np.float32))

    # stereoCalibrate with iterative per-view outlier rejection.
    idx = list(range(len(obj_pts)))
    for _ in range(4):
        o = [obj_pts[k] for k in idx]; a1 = [img1[k] for k in idx]; a2 = [img2[k] for k in idx]
        ret = cv2.stereoCalibrateExtended(
            o, a1, a2, intr1.camera_matrix, intr1.dist_coeffs,
            intr2.camera_matrix, intr2.dist_coeffs, intr1.image_size,
            np.eye(3), np.zeros(3), flags=cv2.CALIB_FIX_INTRINSIC)
        rms, R, T, per = ret[0], ret[5], ret[6], ret[-1]
        err = per.reshape(-1, 2).max(axis=1) if per.size else np.zeros(len(o))
        keep = err <= max(1.5, 2.5 * np.median(err))
        if keep.all() or keep.sum() < 4:
            break
        idx = [idx[k] for k in range(len(idx)) if keep[k]]

    extr = StereoExtrinsics(R, T, float(rms), len(idx))
    extr.save(out)
    say(f"Stereo: pairs={len(idx)}  RMS={rms:.3f}px  baseline={extr.baseline_m():.3f}m"
        f"  -> {out} ({'GOOD' if rms < 1.5 else 'still high'})")
    return extr, float(rms), len(idx)


if __name__ == "__main__":
    solve_extrinsics("data/cam1_extrinsics.MOV", "data/cam2_extrinsics.MOV")
