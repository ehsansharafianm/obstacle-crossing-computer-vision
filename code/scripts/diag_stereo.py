"""Diagnose stereo correspondence/intrinsics quality on matched still holds."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, Intrinsics  # noqa: E402
from run_stereo import scan, estimate_offset  # noqa: E402


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


def pnp_err(objp, imgp, K, d):
    ok, r, t = cv2.solvePnP(objp, imgp, K, d)
    if not ok:
        return 1e9
    proj, _ = cv2.projectPoints(objp, r, t, K, d)
    return float(np.sqrt(np.mean(np.sum((imgp - proj.reshape(-1, 2)) ** 2, axis=1))))


spec = BoardSpec.from_measured_json("calibration/board_measured_large.json")
board_obj = spec.board().getChessboardCorners()
intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
print(f"cam1 intrinsics fx={intr1.camera_matrix[0,0]:.0f} cx={intr1.camera_matrix[0,2]:.0f}")
print(f"cam2 intrinsics fx={intr2.camera_matrix[0,0]:.0f} cx={intr2.camera_matrix[0,2]:.0f}")

_, d1, det1 = scan("data/cam1_extrinsics.MOV", spec)
_, d2, det2 = scan("data/cam2_extrinsics.MOV", spec)
offset = estimate_offset(det1, det2, max(d1, d2))
h1, h2 = make_holds(det1), make_holds(det2)
t2h = np.array([h[0] for h in h2])
print(f"\n{'pair':>4} {'shared':>6} {'cam1/intr1':>11} {'cam1/intr2':>11} {'cam2/intr2':>11} {'cam2/intr1':>11}")
used = set()
for t1, c1, i1, _ in h1:
    j = int(np.argmin(np.abs(t2h - (t1 - offset))))
    if j in used or abs(t2h[j] - (t1 - offset)) > 0.6:
        continue
    used.add(j)
    c2, i2 = h2[j][1], h2[j][2]
    shared = np.intersect1d(i1, i2)
    if len(shared) < 8:
        continue
    m1 = {int(v): c1[k] for k, v in enumerate(i1)}
    m2 = {int(v): c2[k] for k, v in enumerate(i2)}
    objp = np.array([board_obj[int(s)] for s in shared], np.float32)
    p1 = np.array([m1[int(s)] for s in shared], np.float32)
    p2 = np.array([m2[int(s)] for s in shared], np.float32)
    e11 = pnp_err(objp, p1, intr1.camera_matrix, intr1.dist_coeffs)
    e22 = pnp_err(objp, p2, intr2.camera_matrix, intr2.dist_coeffs)
    _, r1, tv1 = cv2.solvePnP(objp, p1, intr1.camera_matrix, intr1.dist_coeffs)
    _, r2, tv2 = cv2.solvePnP(objp, p2, intr2.camera_matrix, intr2.dist_coeffs)
    R1, _ = cv2.Rodrigues(r1); R2, _ = cv2.Rodrigues(r2)
    R_rel = R2 @ R1.T
    t_rel = (tv2 - R_rel @ tv1).ravel()
    rvec_rel, _ = cv2.Rodrigues(R_rel)
    print(f"{len(used):>4} {len(shared):>6}  pnp1={e11:.2f} pnp2={e22:.2f}  "
          f"Rrel(deg)=[{np.degrees(rvec_rel[0,0]):6.1f},{np.degrees(rvec_rel[1,0]):6.1f},{np.degrees(rvec_rel[2,0]):6.1f}]  "
          f"t=[{t_rel[0]:5.2f},{t_rel[1]:5.2f},{t_rel[2]:5.2f}]")
print("\nIf Rrel and t are consistent across pairs -> real geometry; derive R,T from these.")
print("If they scatter -> planar pose ambiguity / too few diverse poses.")
