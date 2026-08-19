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


def _settled_corners(video, det, max_samples=120, tol_px=25.0):
    """Median 2D board-corner positions over the board's STATIONARY period.

    The floor board is placed by hand (it moves while being set down) and the two
    cameras are NOT time-synced -- so a moving board can't be triangulated across
    cameras (frame f in cam1 and cam2 are different instants). We therefore use
    only the settled position: the densest cluster of board-centre locations over
    the clip, and the median corner positions there. Returns {corner_id: (x, y)}
    or None if the board is never found.
    """
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, n // max_samples)
    frames = []
    for f in range(0, n, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, im = cap.read()
        if not ok:
            continue
        c, i = detect_board(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), det)
        if i is None or len(i) < 6:
            continue
        c = np.asarray(c).reshape(-1, 2)
        frames.append((c.mean(0), {int(v): c[k] for k, v in enumerate(i.flatten())}))
    cap.release()
    if len(frames) < 3:
        return None
    centres = np.array([f[0] for f in frames])
    # densest cluster of board centres = the settled (hands-off) position
    counts = [(np.linalg.norm(centres - ctr, axis=1) < tol_px).sum() for ctr in centres]
    ref = centres[int(np.argmax(counts))]
    keep = [fr for fr in frames if np.linalg.norm(fr[0] - ref) < tol_px]
    acc = {}
    for _, cmap in keep:
        for i, xy in cmap.items():
            acc.setdefault(i, []).append(xy)
    return {i: np.median(v, axis=0) for i, v in acc.items()}


def _board_corners_3d(cam1_video, cam2_video, spec, intr1, intr2, extr,
                      max_frames=40):
    """Triangulate the floor board's corners from each camera's SETTLED view.

    Returns (world_ids, board_xyz(N,3) in board coords, cam_xyz(N,3) in cam1 frame).
    Because the board is stationary, the two cameras' settled views correspond
    even without time sync -- so we take each camera's median corner positions
    over its stationary period, then triangulate once.
    """
    board_obj = spec.board().getChessboardCorners()      # (Ncorners,3), board frame
    det = make_detector(spec)
    m1 = _settled_corners(cam1_video, det)
    m2 = _settled_corners(cam2_video, det)
    if m1 is None or m2 is None:
        raise RuntimeError("Floor board not found / not stationary in one camera.")
    ids = sorted(set(m1) & set(m2))
    if len(ids) < 6:
        raise RuntimeError(f"Only {len(ids)} floor board corners shared by both cameras.")
    p1 = np.array([m1[i] for i in ids], float)
    p2 = np.array([m2[i] for i in ids], float)
    cam_xyz = triangulate_stereo(p1, p2, intr1.camera_matrix, intr1.dist_coeffs,
                                 intr2.camera_matrix, intr2.dist_coeffs, extr.R, extr.t)
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
