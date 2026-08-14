"""Split-half stability check for an intrinsics frame set.

Calibrate on even-indexed vs odd-indexed frames separately. If the two focal
lengths agree closely, the calibration is well-constrained; if they diverge,
the frames don't pin the lens down (need more coverage / tilt / depth variety).

Usage (from code/):
    .venv\\Scripts\\python.exe scripts\\check_calib_stability.py data\\intrinsics_cam1
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, calibrate_intrinsics  # noqa: E402

IMG_EXT = (".png", ".jpg", ".jpeg")


def main() -> None:
    folder = sys.argv[1]
    spec = (BoardSpec.from_measured_json("calibration/board_measured.json")
            if Path("calibration/board_measured.json").exists() else BoardSpec())
    paths = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in IMG_EXT)
    even, odd = paths[::2], paths[1::2]
    print(f"{folder}: {len(paths)} frames -> even {len(even)}, odd {len(odd)}")

    ie = calibrate_intrinsics(even, spec, verbose=False)
    io = calibrate_intrinsics(odd, spec, verbose=False)
    fe, fo = ie.camera_matrix[0, 0], io.camera_matrix[0, 0]
    ce, co = ie.camera_matrix[0, 2], io.camera_matrix[0, 2]
    print(f"  fx: even {fe:.1f}  vs  odd {fo:.1f}   -> diff {abs(fe-fo):.1f} px "
          f"({abs(fe-fo)/((fe+fo)/2)*100:.1f}%)")
    print(f"  cx: even {ce:.1f}  vs  odd {co:.1f}   -> diff {abs(ce-co):.1f} px")
    ok = abs(fe - fo) / ((fe + fo) / 2) < 0.02
    print("  VERDICT:", "STABLE (well-constrained)" if ok
          else "UNSTABLE (needs a better video)")


if __name__ == "__main__":
    main()
