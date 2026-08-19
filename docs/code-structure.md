# Code Structure

How the code is organised. Engineering lives in `code/`; see [[progress-log]]
for what each piece achieved and [[automated-pipeline]] for the target system.

## Layout
```
code/
  src/occ/        Python package — the pipeline engine (import as `occ.*`)
  scripts/        runnable entry points (calibration, trajectories, intrinsics)
  run_calib.bat   wrapper: run_calib N  → build_calibration.py
  run_test.bat    wrapper: run_test  N  → build_foot_trajectory.py
  sessions/       TEST sessions:  testNN/ (2 clips → CSV + plot + run.txt)
  calibration/    CALIB sessions: calibNN/  +  shared/active artifacts at root
  tests/          synthetic ground-truth tests
  data/, results/ raw videos + old scratch                 (git-ignored)
matlab/           plot_trajectory.m (results viewer; takes a test id)
slides/           advisor presentation (pptx + build_deck.js)
```
See [[session-workflow]] for the calibrate → record → process loop.

## The `occ` package (engine)
| Module | Responsibility |
|---|---|
| `calibration.py` | ChArUco board spec, board image generation, corner detection, **intrinsic** calibration (with outlier rejection). `BoardSpec.from_measured_json`. |
| `stereo.py` | **Stereo extrinsics** (`CALIB_FIX_INTRINSIC`) — relative camera pose from board pairs. `StereoExtrinsics` (R, t, save/load). |
| `reconstruct.py` | **Triangulation** — `triangulate_stereo` (pair) and `triangulate_nview` (DLT, for a 3rd camera). Projection matrices, reprojection error. |
| `accuracy_check.py` | **Rod/wand validation** — reconstruct known-length object, report mm error by axis. |
| `tracking.py` | **Coloured-marker detection & tracking** — HSV ranges (`COLOR_RANGES`), blob detection, `detect_wand`, `detect_foot` (purple toe + green heel via `FOOT_TOE_COLOR`/`FOOT_HEEL_COLOR`, closest-pair gating), `track_markers`. |
| `filtering.py` | **Trajectory cleaning** — velocity outlier rejection, gap-fill, Butterworth low-pass, `clean_trajectory`. |
| `worldframe.py` | **World-frame transform** — floor board (settled/still period) → camera→world rigid transform (Z = height). `WorldTransform` (apply/save/load), Kabsch. |
| `audiosync.py` | **Camera sync from a shared clap** — `clap_offset` aligns the two clips by the loudest-isolated audio peak (needs `imageio-ffmpeg`). |

## Scripts (run from `code/`)
**Main workflow** (one command each; double-click wrappers `run_calib.bat` / `run_test.bat`)
- `build_calibration.py` — **`run_calib N [normal|large]`**: stereo extrinsics
  (`run_stereo_ransac`) + world frame from a session's 4 board clips → active calibration.
- `build_foot_trajectory.py` — **`run_test N`**: track markers → clap-sync → triangulate →
  rigid-pair + plausibility filter → world frame → CSV + plot.

**Intrinsics (per lens, rarely rerun)**
- `make_calib_board.py` / `make_big_calib_board.py` — generate printable ChArUco boards (small / big tiled).
- `extract_calib_frames.py` — pull sharp, pose-diverse frames from a board video.
- `run_intrinsics.py` — calibrate one camera → `calibration/intrinsics_<cam>.npz`.
- `check_calib_stability.py` — split-half focal-length stability test.

**Extrinsics internals & validation**
- `run_stereo_ransac.py` — **extrinsics** by geometric (time-free) hold matching (imported by `build_calibration`).
- `run_stereo.py` — provides the board-scan helper `scan` used by `run_stereo_ransac`.
- `run_rod_test.py` — rod/wand accuracy check → mm error (uses `occ.accuracy_check`).
- `build_wand_trajectory.py` — moving-wand trajectory (validation of the moving chain).

## Tests
- `test_geometry_synthetic.py` — triangulation & extrinsics recovery vs. ground truth.
- `test_accuracy_check_synthetic.py` — rod accuracy-check math.

## Calibration artifacts (the reusable "profile")
- `intrinsics_cam1.npz`, `intrinsics_cam2.npz` — per-lens (once per iPad).
- `stereo_extrinsics.npz` — camera pair pose (per setup).
- `world_transform.npz` — camera→floor frame (per setup).
- `board_measured*.json` — true printed board sizes; `capture_settings.json`; `rod_markers.json`;
  `*_result.json` — recorded result summaries.

## Pipeline data flow
```
videos ─▶ tracking (2D marker px) ─▶ sync (time align) ─▶ reconstruct (3D, cam frame)
      ─▶ worldframe (Z = height) ─▶ filtering (clean) ─▶ CSV (X/Y/Z + time) ─▶ MATLAB viewer
calibration/ (intrinsics + extrinsics + world_transform) feeds the reconstruct & worldframe steps.
```
