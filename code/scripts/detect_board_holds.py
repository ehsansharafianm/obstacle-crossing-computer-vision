"""Detect 'hold' segments (board held still) in a board video.

Used for stereo extrinsics: the operator holds the board still ~2 s at each pose.
Each such still segment gives one usable frame per camera. This reports how many
holds each video contains so the pairing step can be built on real structure.

Usage (from code/):
    .venv\\Scripts\\python.exe scripts\\detect_board_holds.py data\\cam1_extrinsics.MOV
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, make_detector, detect_board  # noqa: E402


def sharpness(gray):
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def find_holds(video, spec, sample_fps=20.0, move_thresh_px=25.0,
               min_hold_s=0.6, min_corners=8, verbose=True):
    detector = make_detector(spec)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 240.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, int(round(fps / sample_fps)))
    min_hold_samples = max(2, int(round(min_hold_s * sample_fps)))

    # Collect sampled detections: (frame_idx, centroid, sharpness, corners, ids)
    dets = []
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            c, i = detect_board(gray, detector)
            if i is not None and len(i) >= min_corners:
                dets.append((idx, c.reshape(-1, 2).mean(axis=0), sharpness(gray),
                             c, i))
            else:
                dets.append((idx, None, 0.0, None, None))
        idx += 1
    cap.release()

    # Group consecutive detections whose centroid barely moves into holds.
    holds = []
    run = []
    for d in dets:
        if d[1] is None:
            if len(run) >= min_hold_samples:
                holds.append(run)
            run = []
            continue
        if run and np.linalg.norm(d[1] - run[-1][1]) > move_thresh_px:
            if len(run) >= min_hold_samples:
                holds.append(run)
            run = [d]
        else:
            run.append(d)
    if len(run) >= min_hold_samples:
        holds.append(run)

    # Representative frame per hold = sharpest sample in the run.
    reps = []
    for run in holds:
        best = max(run, key=lambda d: d[2])
        reps.append({"frame": best[0], "corners": best[3], "ids": best[4],
                     "n_corners": len(best[4])})
    if verbose:
        dur = total / fps
        print(f"{video}")
        print(f"  {total} frames, {fps:.1f} fps, ~{dur:.0f}s | detected board in "
              f"{sum(1 for d in dets if d[1] is not None)}/{len(dets)} samples")
        print(f"  HOLDS found: {len(reps)}")
        for k, r in enumerate(reps):
            print(f"    hold {k+1:2d}: frame {r['frame']:6d}, {r['n_corners']} corners")
    return reps


if __name__ == "__main__":
    board_json = sys.argv[2] if len(sys.argv) > 2 else "calibration/board_measured.json"
    spec = (BoardSpec.from_measured_json(board_json)
            if Path(board_json).exists() else BoardSpec())
    print(f"(using board {board_json})")
    find_holds(sys.argv[1], spec)
