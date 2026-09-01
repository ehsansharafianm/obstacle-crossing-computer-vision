"""Generate a printable ChArUco calibration board.

Run from the `code/` directory:

    .venv\\Scripts\\python.exe scripts\\make_calib_board.py

Prints a PNG to calibration/charuco_board.png. Print it at 100% scale (NO
"fit to page"), tape it to a rigid flat surface, then MEASURE one square with
calipers and use that measured value as square_len_m during calibration.
"""
import sys
from pathlib import Path

import cv2

# Make `occ` importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, generate_board_image, make_detector, detect_board  # noqa: E402


def main() -> None:
    spec = BoardSpec()  # 8x6, 30mm squares, 23mm markers, DICT_5X5_100
    from occ.paths import CALIB_ACTIVE
    out_dir = CALIB_ACTIVE
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "charuco_board.png"

    img = generate_board_image(spec, dpi=300)
    cv2.imwrite(str(out_path), img)
    print(f"Wrote {out_path}  ({img.shape[1]}x{img.shape[0]} px @ 300 dpi)")
    print(f"Board: {spec.squares_x}x{spec.squares_y}, "
          f"square={spec.square_len_m*1000:.0f} mm, "
          f"marker={spec.marker_len_m*1000:.0f} mm, dict={spec.dict_name}")

    # --- round-trip self-test: detect the board in its own rendered image ---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    corners, ids = detect_board(gray, make_detector(spec))
    n_expected = (spec.squares_x - 1) * (spec.squares_y - 1)
    n_found = 0 if ids is None else len(ids)
    print(f"\nSelf-test: detected {n_found}/{n_expected} interior corners "
          f"in the rendered board.")
    print("PASS" if n_found == n_expected else "WARN: detector missed corners")


if __name__ == "__main__":
    main()
