"""Rod accuracy check: reconstruct the 4-marker wand, compare to known distances.

Uses the fixed intrinsics + stereo extrinsics to triangulate the coloured wand
markers, then reports reconstruction error (mm) vs the measured ground-truth
distances. Known distances also self-validate which cross-camera frame pairs are
truly simultaneous (a wrong pair reconstructs garbage distances).
"""
import json
import sys
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.reconstruct import triangulate_stereo  # noqa: E402

GT = json.loads(Path("calibration/rod_markers.json").read_text())["known_distances_mm"]
KNOWN = sorted(GT.values())  # [124.65, 146.64, 205.0, 242.4]


def blobs(mask):
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, _, stats, cent = cv2.connectedComponentsWithStats(mask)
    return [(float(cent[k][0]), float(cent[k][1]), int(stats[k, 4]))
            for k in range(1, n) if 15 < stats[k, 4] < 3000]


def detect_wand(img):
    """Return (2 red pts, 2 teal pts) clustered on the wand, or None."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    red = cv2.inRange(hsv, (0, 100, 100), (8, 255, 255)) | cv2.inRange(hsv, (172, 100, 100), (180, 255, 255))
    teal = cv2.inRange(hsv, (78, 50, 100), (98, 255, 255))
    R, T = blobs(red), blobs(teal)
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
                bd, best = spread, (np.array([p[:2] for p in rr]),
                                    np.array([p[:2] for p in tt]))
    return best


def scan(video, sample_fps=15.0):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    step = max(1, int(round(fps / sample_fps)))
    out, idx = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx % step == 0:
            w = detect_wand(f)
            if w is not None:
                allpts = np.vstack(w)
                out.append((idx / fps, w[0], w[1], allpts.mean(0)))
        idx += 1
    cap.release()
    return out


def holds(dets, move_px=18.0, min_dur_s=0.3):
    hs, run = [], []
    for t, r, tl, ctr in dets:
        if run and (t - run[-1][0] > 0.25 or np.linalg.norm(ctr - run[-1][3]) > move_px):
            if run[-1][0] - run[0][0] >= min_dur_s:
                hs.append(run[len(run) // 2])
            run = []
        run.append((t, r, tl, ctr))
    if run and run[-1][0] - run[0][0] >= min_dur_s:
        hs.append(run[len(run) // 2])
    return hs  # each: (t, reds(2,2), teals(2,2), centroid)


def match_and_triangulate(reds1, teals1, reds2, teals2, intr1, intr2, F, R, T):
    """Epipolar-match same-colour markers across cameras, triangulate 4 points."""
    def epi_assign(p1s, p2s):
        # 2x2: pick assignment minimising epipolar-line distance
        def line_dist(p1, p2):
            l = F @ np.array([p1[0], p1[1], 1.0])
            return abs(l @ np.array([p2[0], p2[1], 1.0])) / np.hypot(l[0], l[1])
        a = line_dist(p1s[0], p2s[0]) + line_dist(p1s[1], p2s[1])
        b = line_dist(p1s[0], p2s[1]) + line_dist(p1s[1], p2s[0])
        return (p2s if a <= b else p2s[::-1])
    r2 = epi_assign(reds1, reds2)
    t2 = epi_assign(teals1, teals2)
    pts1 = np.vstack([reds1, teals1])
    pts2 = np.vstack([r2, t2])
    X = triangulate_stereo(pts1, pts2, intr1.camera_matrix, intr1.dist_coeffs,
                           intr2.camera_matrix, intr2.dist_coeffs, R, T)
    return X  # (4,3) metres, cam1 frame


def main():
    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr = StereoExtrinsics.load("calibration/stereo_extrinsics.npz")
    R, T = extr.R, extr.t.reshape(3, 1)
    E = np.cross(np.eye(3), T.ravel()) @ R
    F = np.linalg.inv(intr2.camera_matrix).T @ E @ np.linalg.inv(intr1.camera_matrix)

    print("Scanning cam1..."); h1 = holds(scan("data/cam1_rod.MOV"))
    print("Scanning cam2..."); h2 = holds(scan("data/cam2_rod.MOV"))
    print(f"still holds: cam1={len(h1)}, cam2={len(h2)}")

    results = []  # (per-known-distance errors mm, X)
    for _, r1, t1, _ in h1:
        best = None
        for _, r2, t2, _ in h2:
            X = match_and_triangulate(r1, t1, r2, t2, intr1, intr2, F, R, T)
            dists = sorted(np.linalg.norm(X[i] - X[j]) * 1000
                           for i, j in combinations(range(4), 2))
            # match each known distance to nearest reconstructed
            errs = [min(abs(k - dd) for dd in dists) for k in KNOWN]
            score = sum(errs)
            if best is None or score < best[0]:
                best = (score, errs, X)
        if best and best[0] < 40:            # accept: all 4 known distances fit
            results.append((best[1], best[2]))

    print(f"\nAccepted simultaneous poses: {len(results)}")
    if not results:
        raise SystemExit("No consistent poses matched — check detection/holds.")
    E = np.array([r[0] for r in results])     # (n, 4) errors per known distance
    print(f"{'distance(mm)':>12} {'mean|err|':>10} {'RMS':>8} {'max':>8}")
    for c, k in enumerate(KNOWN):
        col = E[:, c]
        print(f"{k:>12.2f} {np.mean(np.abs(col)):>10.2f} "
              f"{np.sqrt(np.mean(col**2)):>8.2f} {np.max(np.abs(col)):>8.2f}")
    allc = E.flatten()
    print(f"\nOVERALL: mean|err|={np.mean(np.abs(allc)):.2f} mm  "
          f"RMS={np.sqrt(np.mean(allc**2)):.2f} mm  max={np.max(np.abs(allc)):.2f} mm  "
          f"({len(results)} poses)")

    # Distribution + best-half capability (isolates outlier poses from the floor).
    per_pose = E.mean(axis=1)
    order = np.argsort(per_pose)
    best_half = E[order[:len(order) // 2]].flatten()
    print(f"per-pose mean err: median={np.median(per_pose):.2f}  "
          f"p25={np.percentile(per_pose,25):.2f}  p75={np.percentile(per_pose,75):.2f} mm")
    print(f"BEST HALF of poses: mean|err|={np.mean(np.abs(best_half)):.2f} mm  "
          f"RMS={np.sqrt(np.mean(best_half**2)):.2f} mm  (system capability)")


if __name__ == "__main__":
    main()
