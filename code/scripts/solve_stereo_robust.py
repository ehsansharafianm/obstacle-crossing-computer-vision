"""Rescue stereo extrinsics from few planar views by resolving pose ambiguity.

Planar solvePnP has a 2-fold ambiguity. For each matched still hold we compute
BOTH pose branches per camera, form all candidate relative poses, and find the
branch combination that agrees across the most pairs (consensus vote). That
recovers the true R,T even when plain stereoCalibrate is confused by too few
views.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
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


def rot_angle(Ra, Rb):
    return np.degrees(np.linalg.norm(cv2.Rodrigues(Ra @ Rb.T)[0]))


spec = BoardSpec.from_measured_json("calibration/board_measured_large.json")
board_obj = spec.board().getChessboardCorners()
intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")

_, dur1, det1 = scan("data/cam1_extrinsics.MOV", spec)
_, dur2, det2 = scan("data/cam2_extrinsics.MOV", spec)
h1, h2 = make_holds(det1), make_holds(det2)
t2h = np.array([h[0] for h in h2])
print(f"holds: cam1={len(h1)}, cam2={len(h2)}")


def build_candidates(offset):
    cands = []
    used, pair_idx = set(), 0
    for t1, c1, i1, _ in h1:
        j = int(np.argmin(np.abs(t2h - (t1 - offset))))
        if j in used or abs(t2h[j] - (t1 - offset)) > 0.8:
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
        n1, rv1, tv1, _ = cv2.solvePnPGeneric(objp, p1, intr1.camera_matrix, intr1.dist_coeffs, flags=cv2.SOLVEPNP_IPPE)
        n2, rv2, tv2, _ = cv2.solvePnPGeneric(objp, p2, intr2.camera_matrix, intr2.dist_coeffs, flags=cv2.SOLVEPNP_IPPE)
        for a in range(n1):
            for b in range(n2):
                R1, _ = cv2.Rodrigues(rv1[a]); R2, _ = cv2.Rodrigues(rv2[b])
                R_rel = R2 @ R1.T
                t_rel = (tv2[b] - R_rel @ tv1[a]).ravel()
                cands.append((pair_idx, R_rel, t_rel, objp, p1, p2))
        pair_idx += 1
    return cands, pair_idx


def consensus(cands):
    best, best_support = None, -1
    for ci in cands:
        sup = set()
        for cj in cands:
            if rot_angle(ci[1], cj[1]) < 5.0 and np.linalg.norm(ci[2] - cj[2]) < 0.15:
                sup.add(cj[0])
        if len(sup) > best_support:
            best_support, best = len(sup), (ci, sup)
    return best_support, best


# Sweep the time offset; pick the alignment that maximises geometric consensus.
best_overall = (-1, None, None, None)
for off_ms in range(-15000, 15001, 100):
    offset = off_ms / 1000.0
    cands, npairs = build_candidates(offset)
    if npairs < 4:
        continue
    sup, best = consensus(cands)
    if sup > best_overall[0]:
        best_overall = (sup, offset, npairs, best)

best_support, offset, npairs, best = best_overall
print(f"Best offset = {offset:.2f}s -> consensus {best_support}/{npairs} pairs agree")
cands, npairs = build_candidates(offset)
ci, support = best

# Gather the closest candidate from each supporting pair; average.
picks = []
for pidx in support:
    same = [c for c in cands if c[0] == pidx]
    picks.append(min(same, key=lambda c: rot_angle(ci[1], c[1]) + np.linalg.norm(ci[2] - c[2])))
R_avg = picks[0][1]  # rotation averaging via successive slerp-ish (few samples)
t_avg = np.mean([p[2] for p in picks], axis=0)
# simple rotation mean: convert to quaternions and average
def R2q(R):
    q = np.empty(4); q[0] = np.sqrt(max(0, 1 + np.trace(R))) / 2
    q[1] = (R[2, 1] - R[1, 2]) / (4 * q[0] + 1e-9)
    q[2] = (R[0, 2] - R[2, 0]) / (4 * q[0] + 1e-9)
    q[3] = (R[1, 0] - R[0, 1]) / (4 * q[0] + 1e-9)
    return q / np.linalg.norm(q)
def q2R(q):
    w, x, y, z = q
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
qs = np.array([R2q(p[1]) for p in picks])
qs = qs * np.sign(qs[:, :1] @ qs[0:1, :1].T)  # align signs
q_avg = qs.mean(axis=0); q_avg /= np.linalg.norm(q_avg)
R_avg = q2R(q_avg)

# Validate: reproject cam1 board pose into cam2 via (R_avg, t_avg).
errs = []
for pidx in support:
    same = [c for c in cands if c[0] == pidx]
    c = min(same, key=lambda c: rot_angle(R_avg, c[1]) + np.linalg.norm(t_avg - c[2]))
    objp, p1, p2 = c[3], c[4], c[5]
    _, rv1, tv1 = cv2.solvePnP(objp, p1, intr1.camera_matrix, intr1.dist_coeffs)
    R1, _ = cv2.Rodrigues(rv1)
    Xc1 = (R1 @ objp.T + tv1).T
    Xc2 = (R_avg @ Xc1.T + t_avg.reshape(3, 1)).T
    proj, _ = cv2.projectPoints(Xc2, np.zeros(3), np.zeros(3), intr2.camera_matrix, intr2.dist_coeffs)
    errs.append(np.sqrt(np.mean(np.sum((p2 - proj.reshape(-1, 2)) ** 2, axis=1))))
rms = float(np.mean(errs))
print(f"baseline = {np.linalg.norm(t_avg):.3f} m")
print(f"cross-camera reprojection RMS = {rms:.2f} px")
if best_support >= 4 and rms < 3.0:
    StereoExtrinsics(R_avg, t_avg.reshape(3, 1), rms, best_support).save("calibration/stereo_extrinsics.npz")
    print("SAVED calibration/stereo_extrinsics.npz  (usable)")
else:
    print("NOT saved - consensus too weak; need a better extrinsics recording.")
