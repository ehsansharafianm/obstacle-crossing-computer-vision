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
    # Red marker (hue ~2). Looser hue for motion; skin (hue ~8) is rejected in
    # detect_foot by the "red nearest the green marker" rule, not by hue alone.
    "red":    [((0, 90, 80), (10, 255, 255)), ((172, 90, 80), (180, 255, 255))],
    "teal":   [((78, 50, 100), (98, 255, 255))],
    # Foot green marker (lime plastic) reads ~hue 39; olive shorts ~hue 101 and
    # yellow obstacles ~hue 25-33 are excluded by the bounds. NOTE: this lime is
    # close to yellow -- for the real study (yellow obstacles) use a truer green.
    "green":  [((34, 90, 70), (99, 255, 255))],
    "yellow": [((22, 90, 120), (35, 255, 255))],
    "blue":   [((100, 90, 80), (120, 255, 255))],
    "orange": [((9, 120, 120), (20, 255, 255))],
    "pink":   [((145, 60, 120), (170, 255, 255))],
    # Foot markers (spherical). Purple toe reads ~hue 124, sat 130+ under the lab
    # lights; sat>=65 & hue>=114 rejects the low-saturation blue couch (~hue 110,
    # sat 55). Red heel ball reads hue ~176 (very saturated); restricting to the
    # HIGH-hue side only (168-180) excludes skin/legs (hue ~5) entirely, which the
    # looser "red" above (and a 0-8 branch) would wrongly pick up.
    "purple":     [((114, 65, 45), (134, 255, 255))],
    "red_marker": [((168, 130, 60), (180, 255, 255))],
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


def detect_foot(frame, max_area=20000, near_px=500):
    """Detect the purple (toe) + red (heel) spherical foot markers.

    Both markers sit on the same shoe, so we return the purple/red pair that are
    CLOSEST together. That mutual-proximity rule rejects purple-ish background
    (blue couch/tape — no red heel nearby) and skin-toned red up the leg (no
    purple toe nearby). If only one colour is visible (the other occluded), the
    largest blob of the visible colour is returned. Returns (toe_xy, heel_xy);
    either may be None.

    max_area is generous (20000 px): the marker is the largest same-colour blob
    and there is no large purple/red background, so when the foot is CLOSE to a
    camera the (correctly large) blob must not be rejected — that would drop
    exactly the close-up frames where accuracy is best.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    purples = detect_blobs(color_mask(hsv, "purple"), max_area=max_area)
    reds = detect_blobs(color_mask(hsv, "red_marker"), max_area=max_area)
    if not purples and not reds:
        return None, None
    if not reds:                                    # heel occluded -> toe only
        return max(purples, key=lambda b: b[2])[:2], None
    if not purples:                                 # toe occluded -> heel only
        return None, max(reds, key=lambda b: b[2])[:2]
    # closest purple-red pair = the two markers on the shoe
    best, bd = None, 1e9
    for p in purples:
        for r in reds:
            d = np.hypot(p[0] - r[0], p[1] - r[1])
            if d < bd:
                bd, best = d, (p, r)
    if bd > near_px:                                # no pair close -> trust largest each
        return max(purples, key=lambda b: b[2])[:2], max(reds, key=lambda b: b[2])[:2]
    p, r = best
    return p[:2], r[:2]


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
