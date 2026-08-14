"""Synthetic validation of occ.accuracy_check.

Build a virtual rig + a known-length rod, and confirm the rod report:
  * reads ~0 error when there is no pixel noise (math is correct), and
  * reads small, sane mm error under realistic pixel noise, per orientation.

Run from code/:  .venv\\Scripts\\python.exe tests\\test_accuracy_check_synthetic.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, Intrinsics          # noqa: E402
from occ.stereo import StereoExtrinsics                    # noqa: E402
from occ.accuracy_check import synthesise_rod, evaluate_rod  # noqa: E402

K = np.array([[1500.0, 0, 960.0], [0, 1500.0, 540.0], [0, 0, 1]])


def _rig():
    a = np.deg2rad(40)
    R2 = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    t2 = -R2 @ np.array([1.6, 0.0, 0.3])
    intr = Intrinsics(K, np.zeros(5), (1920, 1080), 0.0, 25, BoardSpec())
    extr = StereoExtrinsics(R2, t2, 0.0, 20)
    return intr, extr, R2, t2


def main() -> None:
    intr, extr, R2, t2 = _rig()
    TRUE = 0.500  # 500 mm rod
    ok = True

    # --- noise-free: report must read ~0 error ---
    s0 = synthesise_rod(TRUE, K, R2, t2, n_per_orient=20, noise_px=0.0)
    r0 = evaluate_rod(s0, TRUE, intr, intr, extr)
    print("[1] noise-free")
    print("   ", r0.summary().replace("\n", "\n    "))
    ok &= r0.max_abs_mm < 1e-6

    # --- realistic noise: small mm error; vertical (Z) is the interesting axis ---
    s1 = synthesise_rod(TRUE, K, R2, t2, n_per_orient=40, noise_px=0.3, seed=1)
    r1 = evaluate_rod(s1, TRUE, intr, intr, extr)
    print("\n[2] with 0.3 px marker noise")
    print("   ", r1.summary().replace("\n", "\n    "))
    ok &= r1.rms_mm < 5.0                      # sane order of magnitude
    ok &= "vertical" in r1.by_label            # per-orientation breakdown present

    print("\n" + ("ALL PASS" if ok else "FAILURE"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
