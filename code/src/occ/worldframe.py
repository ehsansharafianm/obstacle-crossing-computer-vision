"""World-frame transform: camera coordinates -> floor world frame.

Triangulation gives 3D points in camera-1's frame (origin at the lens, Z = depth).
For meaningful output we transform into a WORLD frame defined by a ChArUco board
laid flat on the floor: Z = up (floor normal), the floor is Z = 0, and X/Y lie in
the floor plane along the board edges.

The transform is a rigid (rotation + translation) map, so it preserves all
distances — the ~2 mm accuracy is unchanged; only the axes/origin move.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .calibration import BoardSpec, Intrinsics, make_detector, detect_board
from .stereo import StereoExtrinsics
from .reconstruct import triangulate_stereo


def kabsch(P: np.ndarray, Q: np.ndarray):
    """Rigid transform (R, t) with R@P + t ≈ Q, least squares. P,Q are (N,3)."""
    Pc, Qc = P.mean(0), Q.mean(0)
    H = (P - Pc).T @ (Q - Qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    t = Qc - R @ Pc
    return R, t


@dataclass
class WorldTransform:
    """Maps camera-1 3D points into the floor world frame: X_world = R @ X_cam + t."""
    R: np.ndarray            # 3x3
    t: np.ndarray            # 3,
    rms_mm: float            # board-fit residual

    def apply(self, X: np.ndarray) -> np.ndarray:
        """X: (...,3) in camera-1 frame -> world frame (same units, metres)."""
        X = np.asarray(X, float)
        flat = X.reshape(-1, 3)
        out = (self.R @ flat.T).T + self.t
        return out.reshape(X.shape)

    def save(self, path):
        np.savez(path, R=self.R, t=self.t, rms_mm=self.rms_mm)

    @staticmethod
    def load(path):
        z = np.load(path)
        return WorldTransform(z["R"], z["t"], float(z["rms_mm"]))


def _board_corners_3d(cam1_video, cam2_video, spec, intr1, intr2, extr,
                      max_frames=40):
    """Triangulate the board's chessboard corners seen by both cameras.

    Returns (world_ids, board_xyz(N,3) in board coords, cam_xyz(N,3) in cam1 frame),
    averaged over frames where a corner is seen by both cameras.
    """
    board_obj = spec.board().getChessboardCorners()      # (Ncorners,3), board frame
    det = make_detector(spec)
    caps = [cv2.VideoCapture(cam1_video), cv2.VideoCapture(cam2_video)]
    n = min(int(c.get(cv2.CAP_PROP_FRAME_COUNT)) for c in caps)
    step = max(1, n // max_frames)
    acc = {}                                             # id -> list of cam1 3D points
    for f in range(0, n, step):
        for c in caps:
            c.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok1, im1 = caps[0].read(); ok2, im2 = caps[1].read()
        if not (ok1 and ok2):
            continue
        c1, i1 = detect_board(cv2.cvtColor(im1, cv2.COLOR_BGR2GRAY), det)
        c2, i2 = detect_board(cv2.cvtColor(im2, cv2.COLOR_BGR2GRAY), det)
        if i1 is None or i2 is None:
            continue
        i1 = i1.flatten(); i2 = i2.flatten()
        m1 = {int(v): c1[k, 0] for k, v in enumerate(i1)}
        m2 = {int(v): c2[k, 0] for k, v in enumerate(i2)}
        shared = np.intersect1d(i1, i2)
        if len(shared) < 6:
            continue
        p1 = np.array([m1[int(s)] for s in shared], float)
        p2 = np.array([m2[int(s)] for s in shared], float)
        X = triangulate_stereo(p1, p2, intr1.camera_matrix, intr1.dist_coeffs,
                               intr2.camera_matrix, intr2.dist_coeffs, extr.R, extr.t)
        for s, x in zip(shared, X):
            acc.setdefault(int(s), []).append(x)
    for c in caps:
        c.release()
    if len(acc) < 6:
        raise RuntimeError(f"Only {len(acc)} board corners seen by both cameras.")
    ids = sorted(acc)
    cam_xyz = np.array([np.median(acc[i], axis=0) for i in ids])
    board_xyz = np.array([board_obj[i] for i in ids])
    return np.array(ids), board_xyz, cam_xyz


def transform_from_points(board_xyz: np.ndarray, cam_xyz: np.ndarray) -> WorldTransform:
    """Build the camera-1 -> world transform from matched board/camera points.

    board_xyz : corner positions in the board's own frame (floor, Z=0 plane).
    cam_xyz   : same corners triangulated in camera-1's frame.
    """
    # board frame -> camera frame:  X_cam = Rb @ X_board + tb
    Rb, tb = kabsch(board_xyz, cam_xyz)
    # world (=board) frame:  X_world = Rb^T @ (X_cam - tb)
    R, t = Rb.T, -Rb.T @ tb

    # Ensure Z points UP: camera sits above the floor, so cam-1 origin (0,0,0)
    # must map to positive world Z. If not, flip X & Z (keeps it right-handed).
    if (R @ np.zeros(3) + t)[2] < 0:
        F = np.diag([-1.0, 1.0, -1.0])
        R, t = F @ R, F @ t

    resid = (R @ cam_xyz.T).T + t                        # world coords of board pts
    rms_mm = float(np.sqrt(np.mean(resid[:, 2] ** 2)) * 1000)  # spread off Z=0
    return WorldTransform(R, t, rms_mm)


def compute_world_transform(cam1_floor, cam2_floor, spec, intr1, intr2, extr,
                            verbose=True) -> WorldTransform:
    """From a floor-board clip, build the camera-1 -> world transform (Z up)."""
    _ids, board_xyz, cam_xyz = _board_corners_3d(cam1_floor, cam2_floor, spec,
                                                 intr1, intr2, extr)
    W = transform_from_points(board_xyz, cam_xyz)
    if verbose:
        cam_h = (W.R @ np.zeros(3) + W.t)[2] * 1000
        print(f"World transform: {len(board_xyz)} board corners, "
              f"floor-flatness residual {W.rms_mm:.2f} mm, "
              f"camera height {cam_h:.0f} mm above floor")
    return W
