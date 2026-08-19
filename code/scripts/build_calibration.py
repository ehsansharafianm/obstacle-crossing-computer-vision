"""Build (or rebuild) the camera calibration for one session: stereo extrinsics
+ world-frame transform, from four clips in calibration/<id>/.

Calibration sessions live in code/calibration/calibNN/. The shared reference
artifacts (intrinsics, board specs, and the active .npz that the foot pipeline
reads) sit in the same code/calibration/ folder, at its root. Test/recording
sessions are the sibling code/sessions/testNN/.

Consumer tripods drift, so recalibrate extrinsics + world at the START of each
recording session, then record all tests without moving the cameras. Intrinsics
(per-lens) are NOT redone here -- they don't depend on camera position, only on
zoom/lens, which you keep at 1x.

Inputs (in calibration/<id>/):
  cam1_ext.MOV,   cam2_ext.MOV     board held STATIC at ~15-20 poses (both cameras)
  cam1_floor.MOV, cam2_floor.MOV   board flat on the floor (defines the world frame)

Outputs: writes stereo_extrinsics.npz + world_transform.npz into the session
folder AND promotes them to the active calibration/ that build_foot_trajectory
reads -- so every test recorded in this session (cameras unmoved) uses it.

Usage (from code/):  python scripts/build_calibration.py 4      (-> calib04)
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))              # scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # src/

import numpy as np  # noqa: E402
from occ.calibration import BoardSpec, Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.worldframe import compute_world_transform  # noqa: E402
from run_stereo_ransac import solve_extrinsics  # noqa: E402

SESS_ROOT = Path("calibration")         # calib sessions live in calibration/calibNN/
ACTIVE = Path("calibration")            # shared artifacts + active calibration at calibration/ root
VIDEO_EXTS = (".MOV", ".mov", ".MP4", ".mp4", ".avi", ".AVI")


def resolve_id(raw):
    s = str(raw).strip()
    return f"calib{int(s):02d}" if s.isdigit() else s


def _norm(s):
    """Lowercase, drop separators -> tolerant matching across naming styles
    (Cam1-extr, cam1_ext, Cam1 Extrinsics all normalise the same way)."""
    return s.lower().replace("-", "").replace("_", "").replace(" ", "")


def find_video(folder, *keys):
    """First video whose normalised name contains ALL keys (e.g. 'cam1','ext')."""
    nkeys = [_norm(k) for k in keys]
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix in VIDEO_EXTS and all(k in _norm(p.stem) for k in nkeys):
            return p
    return None


BOARDS = {
    "normal": "calibration/board_measured.json",       # ~28.5 mm squares (~23x17 cm)
    "small":  "calibration/board_measured.json",
    "large":  "calibration/board_measured_large.json",  # ~62.9 mm squares (~50x38 cm)
    "big":    "calibration/board_measured_large.json",
}


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: build_calibration.py <id> [board]   "
                         "(e.g. 4  or  4 normal  or  4 large)")
    cid = resolve_id(sys.argv[1])
    # Which calibration board was filmed. Default large (the tiled board) for
    # back-compat; pass 'normal' when the cameras are close enough to use the
    # smaller board. Both are the same 8x6 DICT_5X5_100 pattern; only size differs.
    board_arg = (sys.argv[2].lower() if len(sys.argv) > 2 else "large")
    board_json = BOARDS.get(board_arg, board_arg)      # allow an explicit path too
    if not Path(board_json).exists():
        raise SystemExit(f"board spec not found: {board_json}  (use 'normal' or 'large')")
    folder = SESS_ROOT / cid
    folder.mkdir(parents=True, exist_ok=True)

    c1e = find_video(folder, "cam1", "ext")
    c2e = find_video(folder, "cam2", "ext")
    c1f = find_video(folder, "cam1", "floor")
    c2f = find_video(folder, "cam2", "floor")
    missing = [n for n, v in [("cam1_ext", c1e), ("cam2_ext", c2e),
                              ("cam1_floor", c1f), ("cam2_floor", c2f)] if v is None]
    if missing:
        raise SystemExit(
            f"\n[{cid}] needs 4 clips in:\n    {folder.resolve()}\n"
            f"  missing: {', '.join(missing)}\n"
            f"    cam1_ext / cam2_ext      = board held STATIC at ~15-20 poses (both cameras)\n"
            f"    cam1_floor / cam2_floor  = board flat on the floor (world frame)\n"
            f"  then re-run:  python scripts/build_calibration.py {cid}\n")

    log = [f"Calibration session: {cid}", ""]

    def say(m=""):
        print(m); log.append(m)

    say(f"[{cid}]  extrinsics: {c1e.name} + {c2e.name}   floor: {c1f.name} + {c2f.name}")
    say(f"  board: {board_json}")

    # --- 1. Stereo extrinsics (relative camera pose) --------------------------
    say("\n-- Stereo extrinsics --")
    extr, rms, npairs = solve_extrinsics(
        c1e, c2e, board_json=board_json,
        out=str(folder / "stereo_extrinsics.npz"), verbose=True)
    say(f"pairs used = {npairs}   RMS = {rms:.3f} px   baseline = {extr.baseline_m():.3f} m")
    if rms >= 1.5:
        say("WARNING: RMS >= 1.5 px -- extrinsics may be poor "
            "(board not held static, or too few distinct poses?)")
    # Promote extrinsics to active BEFORE the world step (world needs it).
    shutil.copy(folder / "stereo_extrinsics.npz", ACTIVE / "stereo_extrinsics.npz")

    # --- 2. World-frame transform (floor plane, Z = up) ----------------------
    say("\n-- World frame (floor) --")
    spec = BoardSpec.from_measured_json(board_json)
    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr_active = StereoExtrinsics.load(ACTIVE / "stereo_extrinsics.npz")
    W = compute_world_transform(str(c1f), str(c2f), spec, intr1, intr2, extr_active)
    cam_h = (W.R @ np.zeros(3) + W.t)[2] * 1000
    say(f"floor-flatness residual = {W.rms_mm:.2f} mm   camera height = {cam_h:.0f} mm")
    if W.rms_mm >= 3.0:
        say("WARNING: floor residual >= 3 mm -- floor board not flat / not well seen?")
    W.save(folder / "world_transform.npz")
    shutil.copy(folder / "world_transform.npz", ACTIVE / "world_transform.npz")

    say("\nActive calibration updated (calibration/stereo_extrinsics.npz + world_transform.npz).")
    say("Every test recorded in THIS session (cameras unmoved) now uses this calibration.")

    (folder / "calib_run.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"\nSaved session copy + run log -> {folder}")


if __name__ == "__main__":
    main()
