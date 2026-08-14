"""Synthetic ground-truth validation of the reconstruction geometry.

No lab footage needed: we build virtual cameras with KNOWN pose, project known
3D points into them, and confirm the pipeline recovers both the camera pose and
the 3D points. This is the correctness proof for the geometry chain
(sign conventions, coordinate frames, projection matrices) before real data.

Run from code/:  .venv\\Scripts\\python.exe tests\\test_geometry_synthetic.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.reconstruct import (  # noqa: E402
    triangulate_stereo, triangulate_nview, projection_matrix, reprojection_error,
)

K = np.array([[1500.0, 0, 960.0], [0, 1500.0, 540.0], [0, 0, 1]])  # 1920x1080
DIST = np.zeros(5)


def _yaw(deg):
    a = np.deg2rad(deg)
    return np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])


def _project(Xc, R, t):
    rvec, _ = cv2.Rodrigues(R)
    pts, _ = cv2.projectPoints(Xc, rvec, t.reshape(3, 1), K, DIST)
    return pts.reshape(-1, 2)


def _pose(yaw_deg, center):
    """World->camera (R, t) for a camera centred at `center`, yawed by `yaw_deg`."""
    R = _yaw(yaw_deg)
    t = -R @ np.asarray(center, float)
    return R, t


def main() -> None:
    rng = np.random.default_rng(0)
    ok = True

    # Ground-truth 3D cloud in a ~1m x 0.8m x 2m volume, 2-4 m deep (cam-1 frame).
    N = 300
    X = np.column_stack([rng.uniform(-0.5, 0.5, N),
                         rng.uniform(-0.4, 0.4, N),
                         rng.uniform(2.0, 4.0, N)])

    # Camera 1 at origin; cameras 2 & 3 converge on the volume (~40 deg each side).
    R1, t1 = np.eye(3), np.zeros(3)
    R2, t2 = _pose(40, [1.6, 0.0, 0.3])
    R3, t3 = _pose(-40, [-1.6, 0.0, 0.3])

    p1, p2, p3 = _project(X, R1, t1), _project(X, R2, t2), _project(X, R3, t3)

    # --- Test 1: stereo triangulation, no noise -> near-exact recovery ---
    Xrec = triangulate_stereo(p1, p2, K, DIST, K, DIST, R2, t2)
    e = np.linalg.norm(Xrec - X, axis=1)
    print(f"[1] stereo triangulation (noise-free): max error = {e.max()*1e6:.3f} um")
    ok &= e.max() < 1e-6

    # --- Test 2: 3-view DLT triangulation, no noise ---
    Pmats = [projection_matrix(K, R1, t1),
             projection_matrix(K, R2, t2),
             projection_matrix(K, R3, t3)]
    X3 = np.array([triangulate_nview([p1[i], p2[i], p3[i]], Pmats) for i in range(N)])
    e3 = np.linalg.norm(X3 - X, axis=1)
    print(f"[2] 3-view triangulation (noise-free): max error = {e3.max()*1e6:.3f} um")
    ok &= e3.max() < 1e-6

    # --- Test 3: realistic pixel noise -> mm-level error; 3 views beats 2 ---
    sigma = 0.3  # px
    p1n = p1 + rng.normal(0, sigma, p1.shape)
    p2n = p2 + rng.normal(0, sigma, p2.shape)
    p3n = p3 + rng.normal(0, sigma, p3.shape)
    X2n = triangulate_stereo(p1n, p2n, K, DIST, K, DIST, R2, t2)
    X3n = np.array([triangulate_nview([p1n[i], p2n[i], p3n[i]], Pmats) for i in range(N)])
    e2n = np.linalg.norm(X2n - X, axis=1) * 1000
    e3n = np.linalg.norm(X3n - X, axis=1) * 1000
    print(f"[3] with {sigma} px noise:  2-cam RMS = {np.sqrt((e2n**2).mean()):.2f} mm"
          f"   3-cam RMS = {np.sqrt((e3n**2).mean()):.2f} mm  (3-cam should be lower)")
    ok &= np.sqrt((e3n**2).mean()) < np.sqrt((e2n**2).mean())

    # --- Test 4: recover extrinsics via cv2.stereoCalibrate (fixed intrinsics) ---
    # Synthesize a planar board seen in many poses by both cameras.
    gx, gy = np.meshgrid(np.linspace(-0.12, 0.12, 7), np.linspace(-0.09, 0.09, 5))
    board_obj = np.column_stack([gx.ravel(), gy.ravel(),
                                 np.zeros(gx.size)]).astype(np.float32)
    obj_pts, ip1, ip2 = [], [], []
    for _ in range(15):
        rvec = rng.normal(0, 0.25, 3)
        Rb, _ = cv2.Rodrigues(rvec)
        Cb = np.array([rng.uniform(-0.3, 0.3), rng.uniform(-0.2, 0.2),
                       rng.uniform(2.5, 3.5)])
        Xw = (Rb @ board_obj.T).T + Cb                 # board points in cam-1 frame
        obj_pts.append(board_obj)
        ip1.append(_project(Xw, R1, t1).astype(np.float32))
        ip2.append(_project(Xw, R2, t2).astype(np.float32))
    rms, *_rest, Rr, tr, _E, _F = cv2.stereoCalibrate(
        obj_pts, ip1, ip2, K.copy(), DIST.copy(), K.copy(), DIST.copy(),
        (1920, 1080), flags=cv2.CALIB_FIX_INTRINSIC)
    ang_err = np.degrees(np.linalg.norm(cv2.Rodrigues(Rr @ R2.T)[0]))
    t_err = np.linalg.norm(tr.ravel() - t2) * 1000
    print(f"[4] extrinsics recovery: RMS = {rms:.4f} px, "
          f"rotation error = {ang_err:.4f} deg, translation error = {t_err:.3f} mm")
    ok &= ang_err < 0.05 and t_err < 0.5

    print("\n" + ("ALL PASS" if ok else "FAILURE — geometry needs review"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
