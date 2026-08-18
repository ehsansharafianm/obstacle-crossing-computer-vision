"""Compute the world-frame transform from a floor-board clip, and (optionally)
re-express a trajectory CSV in world coordinates (Z = height above floor).

Usage (from code/):
  # compute + save the transform (big board flat on the floor, both cameras):
  .venv\\Scripts\\python.exe scripts\\compute_worldframe.py data\\cam1_floor.MOV data\\cam2_floor.MOV

  # also convert a trajectory to world coords:
  .venv\\Scripts\\python.exe scripts\\compute_worldframe.py data\\cam1_floor.MOV data\\cam2_floor.MOV ^
      --traj results\\foot_trajectory.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.worldframe import compute_world_transform, WorldTransform  # noqa: E402


def convert_csv(in_csv, out_csv, W):
    rows = list(csv.reader(open(in_csv)))
    hdr = rows[0]
    marks = sorted({h[:-5] for h in hdr if h.endswith("_x_mm")},
                   key=lambda m: hdr.index(m + "_x_mm"))
    idx = {m: [hdr.index(f"{m}_{a}_mm") for a in "xyz"] for m in marks}
    ti = hdr.index("time_s")
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(hdr)
        for r in rows[1:]:
            out = list(r)
            for m in marks:
                vals = [r[i] for i in idx[m]]
                if all(v != "" for v in vals):
                    X = np.array([float(v) for v in vals]) / 1000.0   # mm -> m, cam frame
                    Xw = W.apply(X) * 1000.0                          # -> world mm
                    for j, a in enumerate(idx[m]):
                        out[a] = f"{Xw[j]:.2f}"
            w.writerow(out)
    print(f"Wrote {out_csv}  (world frame: Z = height above floor, mm)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cam1_floor")
    ap.add_argument("cam2_floor")
    ap.add_argument("--board", default="calibration/board_measured_large.json")
    ap.add_argument("--traj", default=None, help="trajectory CSV to convert to world frame")
    args = ap.parse_args()

    spec = BoardSpec.from_measured_json(args.board)
    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr = StereoExtrinsics.load("calibration/stereo_extrinsics.npz")

    W = compute_world_transform(args.cam1_floor, args.cam2_floor, spec, intr1, intr2, extr)
    out = Path("calibration/world_transform.npz")
    W.save(out)
    print(f"Saved {out}")

    if args.traj:
        p = Path(args.traj)
        convert_csv(args.traj, str(p.with_name(p.stem + "_world.csv")), W)


if __name__ == "__main__":
    main()
