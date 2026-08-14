"""Stereo extrinsics — relative pose of a camera pair.

This is the per-session half of calibration (intrinsics are done once per iPad;
see occ.calibration). We keep the pre-computed intrinsics FIXED and solve only
for the rotation R and translation t between the two cameras — that is what
`CALIB_FIX_INTRINSIC` does, and it is why splitting intrinsics out first makes
the per-session job small and stable.

Requires SYNCHRONISED image pairs: the board in the same physical pose captured
by both cameras at the same instant. ChArUco lets the two cameras see different
(partial) subsets of the board and still contribute — only the corner IDs seen
by BOTH are used for each pair.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .calibration import BoardSpec, Intrinsics


@dataclass
class StereoExtrinsics:
    R: np.ndarray            # 3x3 rotation, camera-2 relative to camera-1
    t: np.ndarray            # 3x1 translation (same unit as board -> metres)
    rms: float               # stereo reprojection error, pixels
    n_pairs_used: int

    def baseline_m(self) -> float:
        """Distance between the two camera centres (sanity check vs. your setup)."""
        return float(np.linalg.norm(self.t))

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path, R=self.R, t=self.t, rms=self.rms,
                 n_pairs_used=self.n_pairs_used)

    @staticmethod
    def load(path: str | Path) -> "StereoExtrinsics":
        z = np.load(path)
        return StereoExtrinsics(z["R"], z["t"], float(z["rms"]),
                                int(z["n_pairs_used"]))


def _matched_points(gray1, gray2, detector, board):
    """Object + image points for corners seen by BOTH cameras in one pair."""
    c1, i1, _, _ = detector.detectBoard(gray1)
    c2, i2, _, _ = detector.detectBoard(gray2)
    if i1 is None or i2 is None:
        return None
    ids1 = i1.flatten()
    ids2 = i2.flatten()
    common = np.intersect1d(ids1, ids2)
    if len(common) < 6:
        return None

    # Corner index -> its object coordinate on the board.
    obj_all = board.getChessboardCorners()          # (Ncorners, 3)
    sel1 = {int(idv): c1[k, 0] for k, idv in enumerate(ids1)}
    sel2 = {int(idv): c2[k, 0] for k, idv in enumerate(ids2)}

    obj, p1, p2 = [], [], []
    for cid in common:
        obj.append(obj_all[int(cid)])
        p1.append(sel1[int(cid)])
        p2.append(sel2[int(cid)])
    return (np.asarray(obj, np.float32),
            np.asarray(p1, np.float32),
            np.asarray(p2, np.float32))


def stereo_calibrate(pairs: list[tuple[str | Path, str | Path]],
                     intr1: Intrinsics, intr2: Intrinsics,
                     spec: BoardSpec, verbose: bool = True) -> StereoExtrinsics:
    """Solve camera-2's pose relative to camera-1 from synchronised board pairs.

    pairs : list of (image_cam1, image_cam2) file paths, one tuple per instant.
    intr1, intr2 : pre-computed intrinsics for each camera (kept fixed).
    """
    board = spec.board()
    detector = cv2.aruco.CharucoDetector(board)

    obj_pts, img_pts1, img_pts2 = [], [], []
    for f1, f2 in pairs:
        im1, im2 = cv2.imread(str(f1)), cv2.imread(str(f2))
        if im1 is None or im2 is None:
            if verbose:
                print(f"  skip (unreadable): {f1} / {f2}")
            continue
        g1 = cv2.cvtColor(im1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(im2, cv2.COLOR_BGR2GRAY)
        m = _matched_points(g1, g2, detector, board)
        if m is None:
            if verbose:
                print(f"  skip (too few shared corners): {f1} / {f2}")
            continue
        o, a, b = m
        obj_pts.append(o)
        img_pts1.append(a)
        img_pts2.append(b)
        if verbose:
            print(f"  ok ({len(o):3d} shared corners): {Path(f1).name} / {Path(f2).name}")

    if len(obj_pts) < 3:
        raise RuntimeError(
            f"Only {len(obj_pts)} usable pairs — capture more board poses "
            f"visible to both cameras.")

    image_size = intr1.image_size
    rms, _K1, _d1, _K2, _d2, R, t, _E, _F = cv2.stereoCalibrate(
        obj_pts, img_pts1, img_pts2,
        intr1.camera_matrix, intr1.dist_coeffs,
        intr2.camera_matrix, intr2.dist_coeffs,
        image_size, flags=cv2.CALIB_FIX_INTRINSIC)

    if verbose:
        print(f"\nStereo calibrated on {len(obj_pts)} pairs  |  RMS = {rms:.4f} px"
              f"  |  baseline = {np.linalg.norm(t):.3f} m")

    return StereoExtrinsics(R, t, float(rms), len(obj_pts))
