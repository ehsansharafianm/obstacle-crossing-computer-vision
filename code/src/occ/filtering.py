"""Trajectory cleaning: outlier rejection, gap-fill, low-pass filtering.

Turns a raw per-frame 3D marker track (with dropouts and triangulation spikes)
into a clean, smooth trajectory ready for metric computation. Reusable across
the automated pipeline; not specific to any marker.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, filtfilt


def reject_velocity_outliers(xyz: np.ndarray, max_step_m: float = 0.08) -> np.ndarray:
    """NaN-out points that jump implausibly far from the last good point.

    Removes triangulation spikes (a point that leaps away then returns). The
    threshold scales with the gap length so genuine fast motion isn't rejected.
    """
    out = xyz.copy()
    last, last_i = None, None
    for i in range(len(xyz)):
        if np.isnan(xyz[i, 0]):
            continue
        if last is not None:
            gap = max(1, i - last_i)
            if np.linalg.norm(xyz[i] - last) > max_step_m * gap:
                out[i] = np.nan
                continue
        last, last_i = xyz[i], i
    return out


def fill_gaps(xyz: np.ndarray, max_gap: int = 12) -> np.ndarray:
    """Linearly interpolate gaps up to `max_gap` frames; leave longer gaps NaN."""
    out = xyz.copy()
    n = len(xyz)
    idx = np.arange(n)
    for a in range(3):
        good = ~np.isnan(xyz[:, a])
        if good.sum() >= 2:
            out[:, a] = np.interp(idx, idx[good], xyz[good, a])
    # re-mask originally-NaN runs longer than max_gap
    isnan = np.isnan(xyz[:, 0])
    i = 0
    while i < n:
        if isnan[i]:
            j = i
            while j < n and isnan[j]:
                j += 1
            if j - i > max_gap:
                out[i:j] = np.nan
            i = j
        else:
            i += 1
    return out


def butter_lowpass(xyz: np.ndarray, fps: float, cutoff_hz: float = 6.0,
                   order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth low-pass, applied per contiguous valid segment."""
    b, a = butter(order, cutoff_hz / (fps / 2.0), btype="low")
    out = xyz.copy()
    good = ~np.isnan(xyz[:, 0])
    i, n = 0, len(xyz)
    minlen = 3 * (max(len(a), len(b)))
    while i < n:
        if good[i]:
            j = i
            while j < n and good[j]:
                j += 1
            if j - i > minlen:
                for ax in range(3):
                    out[i:j, ax] = filtfilt(b, a, xyz[i:j, ax])
            i = j
        else:
            i += 1
    return out


def clean_trajectory(xyz: np.ndarray, fps: float, max_step_m: float = 0.08,
                     max_gap: int = 12, cutoff_hz: float = 6.0) -> np.ndarray:
    """Full chain: reject spikes -> fill short gaps -> low-pass filter."""
    x = reject_velocity_outliers(xyz, max_step_m)
    x = fill_gaps(x, max_gap)
    x = butter_lowpass(x, fps, cutoff_hz)
    return x
