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
    "yellow": [((22, 90, 120), (35, 255, 255))],
    "blue":   [((100, 90, 80), (120, 255, 255))],
    "orange": [((9, 120, 120), (20, 255, 255))],
    # --- Six-marker study set (test07 on): two feet + ground, all spherical ----
    # Measured under the lab lights: purple 124, green 48, teal 98, pink 165,
    # red 177. Ranges are spaced to keep them apart AND away from clutter (the
    # couch sliver reads teal-ish ~hue 107; skin ~hue 5). Feet use closest-pair
    # gating so same-colour clutter without its partner nearby is rejected.
    "purple":     [((114, 65, 45), (134, 255, 255))],   # left toe
    "green":      [((34, 90, 60), (75, 255, 255))],      # left heel (upper<teal)
    "pink":       [((148, 90, 70), (172, 255, 255))],    # right toe (upper<red)
    "teal":       [((88, 150, 60), (101, 255, 255))],    # right heel. Marker hue ~96-98, S 150-231; hue cap 101 + S>=150 exclude blue-grey shorts (hue ~105, S~130) that sit right at the marker's edge
    # Obstacle reds are ORANGE-RED (hue ~3-9), so BOTH hue ends are needed. Skin
    # (~hue 5-15) and the orange support poles (~hue 16-25) overlap the low end, so
    # detect_round_blobs adds a shape gate; the high saturation floor drops the
    # low-sat floor. Upper bound 12 stays below the orange poles (>=16).
    "red_ground": [((0, 150, 80), (12, 255, 255)), ((170, 150, 80), (180, 255, 255))],
    # legacy alias used by the single-foot detector
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


def detect_round_blobs(mask, min_area=25, max_area=6000, min_circ=0.55, min_fill=0.6):
    """Like detect_blobs but keeps only ROUND, well-filled components, for the
    spherical obstacle red markers whose orange-red hue overlaps skin and the
    orange support poles. Bare limbs and equipment are large and irregular
    (low circularity 4*pi*A/P^2, low bounding-box fill A/(w*h)), so shape rejects
    them where hue alone cannot. Returns (x, y, area), largest first."""
    n, lab, stats, cent = cv2.connectedComponentsWithStats(mask)
    out = []
    for k in range(1, n):
        a = int(stats[k, 4])
        w, h = int(stats[k, 2]), int(stats[k, 3])
        if not (min_area < a < max_area) or w * h == 0 or a / (w * h) < min_fill:
            continue
        comp = (lab == k).astype(np.uint8)
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            continue
        per = cv2.arcLength(cnts[0], True)
        if per <= 0 or 4 * np.pi * a / (per * per) < min_circ:
            continue
        out.append((float(cent[k][0]), float(cent[k][1]), a))
    return sorted(out, key=lambda b: b[2], reverse=True)


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


# Which COLOR_RANGES entry is on each foot marker. Change these two lines when
# the marker colours change (test06 onward: purple toe + green heel).
FOOT_TOE_COLOR = "purple"
FOOT_HEEL_COLOR = "green"


def detect_foot(frame, max_area=20000, near_px=500):
    """Detect the toe + heel spherical foot markers (colours per FOOT_*_COLOR).

    Both markers sit on the same shoe, so we return the toe/heel pair that are
    CLOSEST together. That mutual-proximity rule rejects same-colour background
    or clutter that isn't near the other marker. If only one colour is visible
    (the other occluded), the largest blob of the visible colour is returned.
    Returns (toe_xy, heel_xy); either may be None.

    max_area is generous (20000 px): the marker is the largest same-colour blob
    and there is no large matching background, so when the foot is CLOSE to a
    camera the (correctly large) blob must not be rejected — that would drop
    exactly the close-up frames where accuracy is best.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    toes = detect_blobs(color_mask(hsv, FOOT_TOE_COLOR), max_area=max_area)
    heels = detect_blobs(color_mask(hsv, FOOT_HEEL_COLOR), max_area=max_area)
    if not toes and not heels:
        return None, None
    if not heels:                                   # heel occluded -> toe only
        return max(toes, key=lambda b: b[2])[:2], None
    if not toes:                                     # toe occluded -> heel only
        return None, max(heels, key=lambda b: b[2])[:2]
    # closest toe-heel pair = the two markers on the shoe
    best, bd = None, 1e9
    for p in toes:
        for r in heels:
            d = np.hypot(p[0] - r[0], p[1] - r[1])
            if d < bd:
                bd, best = d, (p, r)
    if bd > near_px:                                # no pair close -> trust largest each
        return max(toes, key=lambda b: b[2])[:2], max(heels, key=lambda b: b[2])[:2]
    p, r = best
    return p[:2], r[:2]


def _closest_pair(toes, heels, near_px):
    """Return the (toe, heel) blobs that are closest together, but ONLY if both a
    toe and a heel exist and they lie within `near_px`. Otherwise (None, None).

    Requiring a real pair rejects same-colour background clutter (e.g. the couch's
    teal, which never has a pink toe beside it). The two foot markers of one shoe
    almost always appear together, so this costs little coverage."""
    if not toes or not heels:
        return None, None
    best, bd = None, 1e9
    for p in toes:
        for r in heels:
            d = np.hypot(p[0] - r[0], p[1] - r[1])
            if d < bd:
                bd, best = d, (p, r)
    if bd > near_px:
        return None, None
    return best[0][:2], best[1][:2]


# The 6-marker study set (test07 on): which COLOR_RANGES entry is each marker.
STUDY_MARKERS = {
    "L_toe": "purple", "L_heel": "green",      # left foot
    "R_toe": "pink",   "R_heel": "teal",       # right foot
    "ground": "red_ground",                    # two static ground markers (same colour)
}


def detect_two_feet_ground(frame, max_area=9000, near_px=500, top_ignore=0.08):
    """Detect the 6-marker set. Returns a dict with L_toe/L_heel/R_toe/R_heel as
    (x, y) or None, and `ground` = list of up to 2 (x, y) red ground markers
    (largest first). Each foot is the CLOSEST pair of its two colours, so
    same-colour clutter with no partner nearby is rejected.

    `top_ignore` blanks the top fraction of the frame before detection — the
    furniture (a teal-ish couch) lives along the top edge and otherwise gets
    picked up as a false heel. The floor markers and feet sit well below it.
    `max_area` also caps out the large couch blob.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    if top_ignore > 0:
        hsv[:int(frame.shape[0] * top_ignore)] = 0

    def bl(color):
        return detect_blobs(color_mask(hsv, color), max_area=max_area)

    L_toe, L_heel = _closest_pair(bl(STUDY_MARKERS["L_toe"]), bl(STUDY_MARKERS["L_heel"]), near_px)
    R_toe, R_heel = _closest_pair(bl(STUDY_MARKERS["R_toe"]), bl(STUDY_MARKERS["R_heel"]), near_px)
    reds = detect_round_blobs(color_mask(hsv, STUDY_MARKERS["ground"]))[:2]
    return {"L_toe": L_toe, "L_heel": L_heel, "R_toe": R_toe, "R_heel": R_heel,
            "ground": [b[:2] for b in reds]}


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
