"""Build (or rebuild) the camera calibration for one session: stereo extrinsics
+ world-frame transform, from the board clips in videos/calibration/<id>/.

Raw board clips live in videos/calibration/calibNN/. The shared reference
artifacts (intrinsics, board specs, and the active .npz the pipeline reads) sit in
results/calibration/active/. Per-calibration results go in results/calibration/calibNN/.
See occ/paths.py for the single source of truth on these locations.

Consumer tripods drift, so recalibrate extrinsics + world at the START of each
recording session, then record all tests without moving the cameras. Intrinsics
(per-lens) are NOT redone here -- they don't depend on camera position, only on
zoom/lens, which you keep at 1x.

Inputs (in videos/calibration/<id>/):
  cam1_ext.mp4,   cam2_ext.mp4     board held STATIC at ~15-20 poses (both cameras)
  cam1_floor.mp4, cam2_floor.mp4   board flat on the floor (defines the world frame)
  cam3_ext.mp4    (optional)       board poses shared with cam2 -> cam2<->cam3 pose,
                                    enabling 3-camera reconstruction. cam2 is the hub,
                                    so cam3 only needs to share poses with cam2 (not cam1).
                                    Needs results/calibration/active/intrinsics_cam3.npz.
                                    cam3_floor is not required (world uses cam1+cam2).

Outputs: writes stereo_extrinsics.npz + world_transform.npz into
results/calibration/<id>/ AND promotes them to results/calibration/active/ that the
trajectory pipeline reads -- so every test recorded this session (cameras unmoved) uses it.

Usage (from code/):  python scripts/build_calibration.py 4      (-> calib04)
"""
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))              # scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # src/

import numpy as np  # noqa: E402
from occ.calibration import BoardSpec, Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.worldframe import compute_world_transform  # noqa: E402
from occ.paths import calib_videos, calib_results, CALIB_ACTIVE  # noqa: E402
from run_stereo_ransac import solve_extrinsics  # noqa: E402

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
    "normal": str(CALIB_ACTIVE / "board_measured.json"),       # ~28.5 mm squares (~23x17 cm)
    "small":  str(CALIB_ACTIVE / "board_measured.json"),
    "large":  str(CALIB_ACTIVE / "board_measured_large.json"),  # ~62.9 mm squares (~50x38 cm)
    "big":    str(CALIB_ACTIVE / "board_measured_large.json"),
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
    video_dir = calib_videos(cid)                    # raw board clips (inputs)
    folder = calib_results(cid)                       # generated .npz + run log
    folder.mkdir(parents=True, exist_ok=True)
    CALIB_ACTIVE.mkdir(parents=True, exist_ok=True)

    c1e = find_video(video_dir, "cam1", "ext")
    c2e = find_video(video_dir, "cam2", "ext")
    c1f = find_video(video_dir, "cam1", "floor")
    c2f = find_video(video_dir, "cam2", "floor")
    missing = [n for n, v in [("cam1_ext", c1e), ("cam2_ext", c2e),
                              ("cam1_floor", c1f), ("cam2_floor", c2f)] if v is None]
    if missing:
        raise SystemExit(
            f"\n[{cid}] needs 4 clips in:\n    {video_dir.resolve()}\n"
            f"  missing: {', '.join(missing)}\n"
            f"    cam1_ext / cam2_ext      = board held STATIC at ~15-20 poses (both cameras)\n"
            f"    cam1_floor / cam2_floor  = board flat on the floor (world frame)\n"
            f"  then re-run:  python scripts/build_calibration.py {cid}\n")

    t_start = time.perf_counter()
    wall_start = datetime.now()
    log = [f"Calibration session: {cid}", ""]

    def say(m=""):
        print(m); log.append(m)

    say(f"[{cid}]  extrinsics: {c1e.name} + {c2e.name}   floor: {c1f.name} + {c2f.name}")
    say(f"  board: {board_json}")

    # --- 1. Stereo extrinsics (relative camera pose) --------------------------
    say("\n-- Stereo extrinsics --")
    extr, rms, npairs = solve_extrinsics(
        c1e, c2e, board_json=board_json,
        intr1_path=str(CALIB_ACTIVE / "intrinsics_cam1.npz"),
        intr2_path=str(CALIB_ACTIVE / "intrinsics_cam2.npz"),
        out=str(folder / "stereo_extrinsics.npz"), verbose=True)
    say(f"pairs used = {npairs}   RMS = {rms:.3f} px   baseline = {extr.baseline_m():.3f} m")
    if rms >= 1.5:
        say("WARNING: RMS >= 1.5 px -- extrinsics may be poor "
            "(board not held static, or too few distinct poses?)")
    # Promote extrinsics to active BEFORE the world step (world needs it).
    shutil.copy(folder / "stereo_extrinsics.npz", CALIB_ACTIVE / "stereo_extrinsics.npz")

    # --- 2. World-frame transform (floor plane, Z = up) ----------------------
    say("\n-- World frame (floor) --")
    spec = BoardSpec.from_measured_json(board_json)
    intr1 = Intrinsics.load(CALIB_ACTIVE / "intrinsics_cam1.npz")
    intr2 = Intrinsics.load(CALIB_ACTIVE / "intrinsics_cam2.npz")
    extr_active = StereoExtrinsics.load(CALIB_ACTIVE / "stereo_extrinsics.npz")
    W = compute_world_transform(str(c1f), str(c2f), spec, intr1, intr2, extr_active)
    cam_h = (W.R @ np.zeros(3) + W.t)[2] * 1000
    say(f"floor-flatness residual = {W.rms_mm:.2f} mm   camera height = {cam_h:.0f} mm")
    if W.rms_mm >= 3.0:
        say("WARNING: floor residual >= 3 mm -- floor board not flat / not well seen?")

    # --- Axis readout: which way +X/+Y point (so you can flip if it's not what you want)
    w1 = W.apply(np.zeros((1, 3)))[0] * 1000                       # cam1 in world
    w2 = W.apply((-extr_active.R.T @ extr_active.t.reshape(3)).reshape(1, 3))[0] * 1000  # cam2
    say(f"Axis check (mm):  cam1 world (X={w1[0]:.0f}, Y={w1[1]:.0f})   "
        f"cam2 world (X={w2[0]:.0f}, Y={w2[1]:.0f})")
    say(f"  +X points toward the {'cam1' if w1[0] > w2[0] else 'cam2'} side; "
        f"+Y toward the {'cam1' if w1[1] > w2[1] else 'cam2'} side.")
    say("  (Set X/Y by how you lay the floor board: origin corner, long edge = +X, short = +Y.)")
    W.save(folder / "world_transform.npz")
    shutil.copy(folder / "world_transform.npz", CALIB_ACTIVE / "world_transform.npz")

    # --- 3. Optional 3rd camera: cam2<->cam3 extrinsics (cam2 is the hub) ------
    c3e = find_video(video_dir, "cam3", "ext")
    intr3_path = CALIB_ACTIVE / "intrinsics_cam3.npz"
    if c3e is not None and intr3_path.exists():
        say("\n-- cam2<->cam3 extrinsics (3rd camera) --")
        extr23, rms23, np23 = solve_extrinsics(
            c2e, c3e, board_json=board_json,
            intr1_path=str(CALIB_ACTIVE / "intrinsics_cam2.npz"),
            intr2_path=str(CALIB_ACTIVE / "intrinsics_cam3.npz"),
            out=str(folder / "stereo_extrinsics_cam2cam3.npz"), verbose=True)
        say(f"pairs used = {np23}   RMS = {rms23:.3f} px   baseline = {extr23.baseline_m():.3f} m")
        if rms23 >= 1.5:
            say("WARNING: cam2<->cam3 RMS >= 1.5 px -- 3rd camera pose may be poor")
        shutil.copy(folder / "stereo_extrinsics_cam2cam3.npz",
                    CALIB_ACTIVE / "stereo_extrinsics_cam2cam3.npz")
        say("cam3 calibrated -> 3-camera reconstruction enabled for this session.")
    else:
        # Stale cam2<->cam3 from a previous setup would silently misplace cam3.
        (CALIB_ACTIVE / "stereo_extrinsics_cam2cam3.npz").unlink(missing_ok=True)
        if c3e is None:
            say("\n(no cam3_ext clip -- 2-camera calibration)")
        else:
            say("\n(cam3_ext found but active intrinsics_cam3.npz missing -- skipping cam3)")

    say("\nActive calibration updated (results/calibration/active/: stereo_extrinsics.npz + world_transform.npz"
        + (" + stereo_extrinsics_cam2cam3.npz" if c3e is not None and intr3_path.exists() else "") + ").")
    say("Every test recorded in THIS session (cameras unmoved) now uses this calibration.")

    elapsed = time.perf_counter() - t_start
    mins, secs = divmod(elapsed, 60)
    say(f"\nRun started:  {wall_start:%Y-%m-%d %H:%M:%S}")
    say(f"Run finished: {datetime.now():%Y-%m-%d %H:%M:%S}")
    say(f"Total processing time: {int(mins)} min {secs:.1f} s  ({elapsed:.1f} s)")
    (folder / "calib_run.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"\nSaved session copy + run log -> {folder}")


if __name__ == "__main__":
    main()
