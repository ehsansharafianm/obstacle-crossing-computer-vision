"""Colored-marker detection & tracking.

Distinct-coloured markers (one colour per marker) make tracking simple and
robust: in each frame, the marker of colour C is the appropriate blob of that
colour. This module detects such markers per frame and links them into 2D
tracks over time — the input to time-synced triangulation (trajectories).

Colour ranges are in OpenCV HSV (H 0-180). Tuned against the rod-test footage;
re-tune per lighting with `tune` if needed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

# HSV (low, high) ranges per colour; red wraps hue so it has two ranges.
COLOR_RANGES = {
    "red":    [((0, 100, 100), (8, 255, 255)), ((172, 100, 100), (180, 255, 255))],
    "teal":   [((78, 50, 100), (98, 255, 255))],
    "green":  [((40, 60, 60), (75, 255, 255))],
    "yellow": [((22, 90, 120), (35, 255, 255))],
    "blue":   [((100, 90, 80), (120, 255, 255))],
    "orange": [((9, 120, 120), (20, 255, 255))],
    "pink":   [((145, 60, 120), (170, 255, 255))],
}


def color_mask(hsv, color):
    m = None
    for lo, hi in COLOR_RANGES[color]:
        part = cv2.inRange(hsv, lo, hi)
        m = part if m is None else (m | part)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))


def detect_blobs(mask, min_area=15, max_area=6000):
    n, _, stats, cent = cv2.connectedComponentsWithStats(mask)
    return [(float(cent[k][0]), float(cent[k][1]), int(stats[k, 4]))
            for k in range(1, n) if min_area < stats[k, 4] < max_area]


def detect_markers(frame, colors, min_area=15, max_area=6000):
    """Per colour, return the largest blob centroid (x, y) or None."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    out = {}
    for c in colors:
        blobs = detect_blobs(color_mask(hsv, c), min_area, max_area)
        out[c] = max(blobs, key=lambda b: b[2])[:2] if blobs else None
    return out


def detect_wand(frame, max_area=800):
    """Return (reds(2,2), teals(2,2)) clustered on the wand, or None.

    The 4 markers are the tightest 2-red + 2-teal cluster, which rejects
    isolated same-colour clutter (blue floor tape, skin).
    """
    from itertools import combinations
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    R = detect_blobs(color_mask(hsv, "red"), max_area=max_area)
    T = detect_blobs(color_mask(hsv, "teal"), max_area=max_area)
    d = lambda a, b: np.hypot(a[0] - b[0], a[1] - b[1])
    R = [r for r in R if any(d(r, t) < 300 for t in T)]
    T = [t for t in T if any(d(t, r) < 300 for r in R)]
    if len(R) < 2 or len(T) < 2:
        return None
    best, bd = None, 1e9
    for rr in combinations(R, 2):
        for tt in combinations(T, 2):
            pts = np.array([p[:2] for p in rr + tt])
            spread = np.linalg.norm(pts.max(0) - pts.min(0))
            if spread < bd:
                bd = spread
                best = (np.array([p[:2] for p in rr]), np.array([p[:2] for p in tt]))
    return best


@dataclass
class Track:
    """2D position over time for one marker (NaN where not detected)."""
    color: str
    t: list = field(default_factory=list)          # seconds
    xy: list = field(default_factory=list)         # (x, y) or (nan, nan)

    def array(self):
        return np.array(self.t), np.array(self.xy)

    @property
    def coverage(self):
        v = np.array([not np.isnan(p[0]) for p in self.xy])
        return float(v.mean()) if len(v) else 0.0


def track_markers(video, colors, max_jump_px=180.0, max_area=6000):
    """Detect + link markers frame by frame. Returns {color: Track}.

    Uses nearest-to-previous gating (max_jump_px) so a spurious same-colour blob
    can't steal the track. One marker per colour assumed.
    """
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    tracks = {c: Track(c) for c in colors}
    last = {c: None for c in colors}
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        for c in colors:
            blobs = detect_blobs(color_mask(hsv, c), max_area=max_area)
            pick = None
            if blobs:
                if last[c] is None:
                    pick = max(blobs, key=lambda b: b[2])[:2]
                else:
                    cands = [b for b in blobs
                             if np.hypot(b[0] - last[c][0], b[1] - last[c][1]) <= max_jump_px]
                    if cands:
                        pick = min(cands, key=lambda b:
                                   np.hypot(b[0] - last[c][0], b[1] - last[c][1]))[:2]
            tracks[c].t.append(idx / fps)
            tracks[c].xy.append(pick if pick is not None else (np.nan, np.nan))
            if pick is not None:
                last[c] = pick
        idx += 1
    cap.release()
    return tracks
