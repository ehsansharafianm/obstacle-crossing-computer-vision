"""3D reconstruction — turn 2D image points into 3D world points.

Two triangulation paths:

* `triangulate_stereo` — fast path for a calibrated camera *pair* (OpenCV's
  `triangulatePoints`), output in camera-1's coordinate frame.
* `triangulate_nview` — linear DLT across *N >= 2* cameras. Use this once a
  third camera is added to fight trail-limb occlusion (design doc §74): a point
  seen by all cameras that see it is reconstructed from every available view.

All 3D output is in the same length unit as the calibration board (metres).
"""
from __future__ import annotations

import cv2
import numpy as np


def projection_matrix(K: np.ndarray, R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """3x4 projection matrix P = K [R | t] for a camera at pose (R, t)."""
    Rt = np.hstack([R, t.reshape(3, 1)])
    return K @ Rt


def triangulate_stereo(pts1: np.ndarray, pts2: np.ndarray,
                       K1: np.ndarray, d1: np.ndarray,
                       K2: np.ndarray, d2: np.ndarray,
                       R: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Triangulate matched points from a calibrated pair.

    pts1, pts2 : (N, 2) pixel coordinates of the SAME points in each camera.
    R, t       : pose of camera 2 relative to camera 1 (from stereo calibration).
    Returns (N, 3) points in camera-1's frame.
    """
    pts1 = np.asarray(pts1, dtype=np.float64).reshape(-1, 1, 2)
    pts2 = np.asarray(pts2, dtype=np.float64).reshape(-1, 1, 2)

    # Undistort to normalised image coordinates (K = identity afterwards).
    n1 = cv2.undistortPoints(pts1, K1, d1).reshape(-1, 2).T  # (2, N)
    n2 = cv2.undistortPoints(pts2, K2, d2).reshape(-1, 2).T

    P1 = np.hstack([np.eye(3), np.zeros((3, 1))])            # camera 1 at origin
    P2 = np.hstack([R, t.reshape(3, 1)])                    # camera 2 relative

    Xh = cv2.triangulatePoints(P1, P2, n1, n2)              # (4, N) homogeneous
    return (Xh[:3] / Xh[3]).T                               # (N, 3)


def triangulate_nview(points_per_cam: list[np.ndarray],
                      proj_mats: list[np.ndarray]) -> np.ndarray:
    """Linear DLT triangulation of ONE point from N >= 2 views.

    points_per_cam : list of (2,) pixel coordinates, one per camera that sees
                     the point. Must already be undistorted (or from a low-
                     distortion lens) — pass points in the same frame as proj_mats.
    proj_mats      : list of 3x4 projection matrices, aligned with points_per_cam.
    Returns (3,) world point.

    For a whole trajectory, call per frame with only the cameras that saw the
    marker in that frame — this is what makes N-view robust to occlusion.
    """
    if len(points_per_cam) != len(proj_mats):
        raise ValueError("points_per_cam and proj_mats must be the same length")
    if len(proj_mats) < 2:
        raise ValueError("need at least 2 views to triangulate")

    rows = []
    for (x, y), P in zip(points_per_cam, proj_mats):
        rows.append(x * P[2] - P[0])
        rows.append(y * P[2] - P[1])
    A = np.asarray(rows)                     # (2N, 4)
    _u, _s, vt = np.linalg.svd(A)
    Xh = vt[-1]
    return Xh[:3] / Xh[3]


def reprojection_error(X: np.ndarray, pts_per_cam: list[np.ndarray],
                       proj_mats: list[np.ndarray]) -> float:
    """Mean pixel reprojection error of a reconstructed point across views."""
    errs = []
    for (x, y), P in zip(pts_per_cam, proj_mats):
        p = P @ np.append(X, 1.0)
        p = p[:2] / p[2]
        errs.append(np.hypot(p[0] - x, p[1] - y))
    return float(np.mean(errs))
