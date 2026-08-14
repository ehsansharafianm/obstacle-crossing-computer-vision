"""Extract good calibration frames from a board video.

Records of the ChArUco board filmed in the LOCKED capture mode (1080p, 1x,
landscape, AE/AF locked). This picks frames that are (a) sharp, (b) have the
board clearly detected, and (c) are spread out in pose — then those frames feed
run_intrinsics.py. Filming a video and extracting beats shooting stills because
it captures the board in the exact video-mode optics used for the experiment.

Usage (from code/):
    .venv\\Scripts\\python.exe scripts\\extract_calib_frames.py ^
        data\\cam1_board.mov data\\intrinsics_cam1 --max 35
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, make_detector, detect_board  # noqa: E402


def sharpness(gray) -> float:
    """Variance of the Laplacian — higher is sharper (less motion blur)."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out_dir")
    ap.add_argument("--max", type=int, default=35, help="max frames to keep")
    ap.add_argument("--min-corners", type=int, default=12,
                    help="require at least this many ChArUco corners")
    ap.add_argument("--sharp-pct", type=float, default=40.0,
                    help="reject frames below this sharpness percentile")
    ap.add_argument("--move-frac", type=float, default=0.06,
                    help="min board-centroid move (frac of width) vs last kept")
    ap.add_argument("--candidates", type=int, default=2500,
                    help="how many frames across the video to inspect for the board")
    ap.add_argument("--board-json", default="calibration/board_measured.json")
    args = ap.parse_args()

    spec = (BoardSpec.from_measured_json(args.board_json)
            if Path(args.board_json).exists() else BoardSpec())
    detector = make_detector(spec)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video: {args.video}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    print(f"Video: {total} frames, {w}px wide")

    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    GX, GY = 6, 4  # image grid for coverage (24 cells)

    def cells_of(corners):
        pts = corners.reshape(-1, 2)
        cx = np.clip((pts[:, 0] / w * GX).astype(int), 0, GX - 1)
        cy = np.clip((pts[:, 1] / h * GY).astype(int), 0, GY - 1)
        return set(zip(cx.tolist(), cy.tolist()))

    # Pass 1: score every ~Nth frame that has the board.
    step = max(1, total // args.candidates)  # inspect ~args.candidates frames
    cands = []  # (frame_idx, sharpness, centroid, covered_cells)
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corners, ids = detect_board(gray, detector)
            if ids is not None and len(ids) >= args.min_corners:
                cands.append((idx, sharpness(gray),
                              corners.reshape(-1, 2).mean(axis=0),
                              cells_of(corners)))
        idx += 1

    if not cands:
        raise SystemExit("No frames with a detectable board — check the video/board.")

    sharp_vals = np.array([c[1] for c in cands])
    thresh = np.percentile(sharp_vals, args.sharp_pct)
    pool = [c for c in cands if c[1] >= thresh]            # drop blurry

    # Phase A — coverage: greedily add the frame that fills the most NEW image
    # cells (tie-break by sharpness). This forces corner/edge coverage, which is
    # what actually constrains focal length & distortion.
    kept, covered = [], set()
    remaining = list(pool)
    while remaining and len(kept) < args.max:
        best = max(remaining, key=lambda c: (len(c[3] - covered), c[1]))
        if len(best[3] - covered) == 0:
            break                                          # coverage saturated
        kept.append(best)
        covered |= best[3]
        remaining.remove(best)

    # Phase B — top-up with sharp, spatially spread frames for pose/depth variety.
    min_move = args.move_frac * w
    centroids = [c[2] for c in kept]
    for c in sorted(remaining, key=lambda c: -c[1]):
        if len(kept) >= args.max:
            break
        if all(np.linalg.norm(c[2] - k) >= min_move for k in centroids):
            kept.append(c)
            centroids.append(c[2])
    print(f"Image-cell coverage: {len(covered)}/{GX*GY} cells")
    kept = sorted((c[0], c[1]) for c in kept)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    want = {f for f, _ in kept}
    saved, idx = 0, 0
    while saved < len(want):
        ok, frame = cap.read()
        if not ok:
            break
        if idx in want:
            cv2.imwrite(str(out / f"frame_{idx:06d}.png"), frame)
            saved += 1
        idx += 1
    cap.release()
    print(f"Kept {saved} sharp, pose-diverse frames -> {out}")
    print("Next: run_intrinsics.py on that folder.")


if __name__ == "__main__":
    main()
