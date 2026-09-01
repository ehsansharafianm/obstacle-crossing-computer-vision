"""Calibrate one camera's intrinsics from a folder of board frames.

Usage (from code/):
    .venv\\Scripts\\python.exe scripts\\run_intrinsics.py data\\intrinsics_cam1 cam1

Saves calibration/intrinsics_<name>.npz and prints the reprojection error
(the real-world quality gate: well under ~1 px is a clean calibration).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, calibrate_intrinsics  # noqa: E402
from occ.paths import CALIB_ACTIVE  # noqa: E402

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images_dir")
    ap.add_argument("name", help="camera name, e.g. cam1")
    ap.add_argument("--board-json", default=str(CALIB_ACTIVE / "board_measured.json"))
    args = ap.parse_args()

    spec = (BoardSpec.from_measured_json(args.board_json)
            if Path(args.board_json).exists() else BoardSpec())
    print(f"Board: {spec.squares_x}x{spec.squares_y}, "
          f"square={spec.square_len_m*1000:.3f} mm\n")

    paths = sorted(p for p in Path(args.images_dir).iterdir()
                   if p.suffix.lower() in IMG_EXT)
    if not paths:
        raise SystemExit(f"No images in {args.images_dir}")
    print(f"Calibrating on {len(paths)} images from {args.images_dir}:")

    intr = calibrate_intrinsics(paths, spec)

    out = CALIB_ACTIVE / f"intrinsics_{args.name}.npz"
    intr.save(out)
    fx, fy = intr.camera_matrix[0, 0], intr.camera_matrix[1, 1]
    cx, cy = intr.camera_matrix[0, 2], intr.camera_matrix[1, 2]
    print(f"\nSaved -> {out}")
    print(f"  fx={fx:.1f}  fy={fy:.1f}  cx={cx:.1f}  cy={cy:.1f}")
    print(f"  RMS reprojection error = {intr.rms_reproj_error:.4f} px  "
          f"({'good' if intr.rms_reproj_error < 1.0 else 'high - review frames'})")


if __name__ == "__main__":
    main()
