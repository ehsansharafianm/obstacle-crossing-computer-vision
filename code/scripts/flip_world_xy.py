"""Rotate the active world frame 180 deg about Z:  X -> -X,  Y -> -Y.

Z (up), all distances, and the calibration accuracy are unchanged -- this only
flips the sign of the two horizontal axes, for when the +X/+Y directions came out
opposite to the convention you want. It rewrites calibration/world_transform.npz
(and the session copy if given). Re-run the trajectory builder to get flipped
coordinates in the .xlsx / plots.

Usage (from code/):
    python scripts/flip_world_xy.py                 # flip the active world frame
    python scripts/flip_world_xy.py calib10         # also update that session copy
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.worldframe import WorldTransform  # noqa: E402

RF = np.diag([-1.0, -1.0, 1.0])            # 180 deg about Z (proper rotation)


def flip(path):
    W = WorldTransform.load(path)
    W.R = RF @ W.R
    W.t = RF @ W.t
    W.save(path)
    print(f"Flipped X/Y in {path}")


def main():
    flip("calibration/world_transform.npz")
    if len(sys.argv) > 1:
        cid = sys.argv[1]
        cid = f"calib{int(cid):02d}" if str(cid).isdigit() else cid
        p = Path("calibration") / cid / "world_transform.npz"
        if p.exists():
            flip(str(p))
    print("Done. Re-run build_multi_trajectory to get flipped (negated X, Y) output.")


if __name__ == "__main__":
    main()
