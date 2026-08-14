"""Calibration accuracy check — the known-length-rod validation.

This is the "trusted measurement" evidence for using the cameras as a PRIMARY
source (design doc §8, §98). Procedure: reconstruct a rigid rod of known length,
placed at many positions/orientations across the volume — INCLUDING VERTICAL,
because clearance is a Z-axis measurement — and report the error in mm.

This module does the geometry + reporting. Getting the two rod-endpoint pixel
locations into a `RodSample` is deliberately left to the caller (manual click,
colour blob, reflective+IR — undecided; open item), so the validation math does
not depend on a marker-detection choice. A manual-click helper is provided for
lab use, and `synthesise_rod` builds ground-truth samples for self-testing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .calibration import Intrinsics
from .reconstruct import triangulate_stereo
from .stereo import StereoExtrinsics


@dataclass
class RodSample:
    """One observation of the two rod endpoints in both cameras.

    p1, p2 : (2, 2) arrays — two endpoint pixel coords in camera 1 / camera 2.
    label  : optional grouping tag, e.g. 'vertical', 'horizontal', 'far'.
    """
    p1: np.ndarray
    p2: np.ndarray
    label: str = "all"


@dataclass
class RodReport:
    true_length_m: float
    n: int
    lengths_m: np.ndarray            # reconstructed length per sample
    errors_mm: np.ndarray            # signed (reconstructed - true), mm
    endpoints: np.ndarray            # (n, 2, 3) reconstructed 3D endpoints
    by_label: dict = field(default_factory=dict)

    @property
    def mean_abs_mm(self) -> float:
        return float(np.mean(np.abs(self.errors_mm)))

    @property
    def rms_mm(self) -> float:
        return float(np.sqrt(np.mean(self.errors_mm ** 2)))

    @property
    def max_abs_mm(self) -> float:
        return float(np.max(np.abs(self.errors_mm)))

    def summary(self) -> str:
        lines = [
            f"Rod accuracy check - true length {self.true_length_m*1000:.2f} mm, "
            f"{self.n} samples",
            f"  mean |error| = {self.mean_abs_mm:.2f} mm",
            f"  RMS  error   = {self.rms_mm:.2f} mm",
            f"  max  |error| = {self.max_abs_mm:.2f} mm",
        ]
        if len(self.by_label) > 1:
            lines.append("  by orientation/region:")
            for lab, r in self.by_label.items():
                lines.append(f"    {lab:12s} n={r['n']:3d}  "
                             f"RMS={r['rms_mm']:.2f} mm  max={r['max_mm']:.2f} mm")
        return "\n".join(lines)


def reconstruct_rod(sample: RodSample, intr1: Intrinsics, intr2: Intrinsics,
                    extr: StereoExtrinsics) -> tuple[float, np.ndarray]:
    """Triangulate a rod's two endpoints; return (length_m, endpoints_3d)."""
    pts1 = np.asarray(sample.p1, float).reshape(2, 2)
    pts2 = np.asarray(sample.p2, float).reshape(2, 2)
    X = triangulate_stereo(pts1, pts2,
                           intr1.camera_matrix, intr1.dist_coeffs,
                           intr2.camera_matrix, intr2.dist_coeffs,
                           extr.R, extr.t)                 # (2, 3)
    length = float(np.linalg.norm(X[0] - X[1]))
    return length, X


def evaluate_rod(samples: list[RodSample], true_length_m: float,
                 intr1: Intrinsics, intr2: Intrinsics,
                 extr: StereoExtrinsics) -> RodReport:
    """Reconstruct every rod sample and summarise error vs. the known length."""
    lengths, endpoints, labels = [], [], []
    for s in samples:
        L, X = reconstruct_rod(s, intr1, intr2, extr)
        lengths.append(L)
        endpoints.append(X)
        labels.append(s.label)

    lengths = np.asarray(lengths)
    endpoints = np.asarray(endpoints)
    errors_mm = (lengths - true_length_m) * 1000.0
    labels = np.asarray(labels)

    by_label = {}
    for lab in dict.fromkeys(labels):                      # preserve order, unique
        m = labels == lab
        e = errors_mm[m]
        by_label[lab] = {
            "n": int(m.sum()),
            "rms_mm": float(np.sqrt(np.mean(e ** 2))),
            "max_mm": float(np.max(np.abs(e))),
            "mean_abs_mm": float(np.mean(np.abs(e))),
        }

    return RodReport(true_length_m, len(samples), lengths, errors_mm,
                     endpoints, by_label)


# --------------------------------------------------------------------------- #
# Ground-truth sample generator (for self-testing this module)
# --------------------------------------------------------------------------- #
def synthesise_rod(true_length_m: float, K, R2, t2, n_per_orient: int = 20,
                   noise_px: float = 0.0, seed: int = 0) -> list[RodSample]:
    """Project a known-length rod at many poses into a virtual camera pair.

    Camera 1 is at the origin; camera 2 has pose (R2, t2). Rods are placed
    horizontally (X), laterally (Y), and VERTICALLY (Z), spanning the volume,
    so the report exercises the per-orientation breakdown.
    """
    import cv2
    rng = np.random.default_rng(seed)
    dist = np.zeros(5)
    r2vec, _ = cv2.Rodrigues(R2)

    def project(Xc):
        pts, _ = cv2.projectPoints(Xc, np.zeros(3), np.zeros(3), K, dist)
        p1 = pts.reshape(-1, 2)
        pts2, _ = cv2.projectPoints(Xc, r2vec, t2.reshape(3, 1), K, dist)
        return p1, pts2.reshape(-1, 2)

    axes = {"horizontal": np.array([1., 0, 0]),
            "lateral":    np.array([0, 1., 0]),
            "vertical":   np.array([0, 0, 1.])}
    samples = []
    for lab, axis in axes.items():
        for _ in range(n_per_orient):
            center = np.array([rng.uniform(-0.4, 0.4),
                               rng.uniform(-0.3, 0.3),
                               rng.uniform(2.2, 3.8)])
            half = axis * (true_length_m / 2.0)
            ends = np.array([center - half, center + half], np.float64)
            p1, p2 = project(ends)
            if noise_px:
                p1 = p1 + rng.normal(0, noise_px, p1.shape)
                p2 = p2 + rng.normal(0, noise_px, p2.shape)
            samples.append(RodSample(p1, p2, lab))
    return samples


# --------------------------------------------------------------------------- #
# Lab helper: manually click the two endpoints in a pair of images
# --------------------------------------------------------------------------- #
def click_rod_endpoints(image1_path, image2_path, label="all") -> RodSample:  # pragma: no cover
    """Interactive: click the 2 rod endpoints in each image (cam1 then cam2).

    Requires a GUI backend; run in the lab, not headless. Click order must be
    consistent (e.g. always the marked end first) so endpoints correspond.
    """
    import cv2
    import matplotlib.pyplot as plt

    def pick(path):
        img = cv2.cvtColor(cv2.imread(str(path)), cv2.COLOR_BGR2RGB)
        plt.figure(figsize=(12, 7))
        plt.imshow(img)
        plt.title(f"{path}\nClick the 2 rod endpoints (same order in both images)")
        pts = plt.ginput(2, timeout=0)
        plt.close()
        return np.asarray(pts, float)

    return RodSample(pick(image1_path), pick(image2_path), label)
