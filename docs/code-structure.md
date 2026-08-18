# Code Structure

How the code is organised. Engineering lives in `code/`; see [[progress-log]]
for what each piece achieved and [[automated-pipeline]] for the target system.

## Layout
```
code/
  src/occ/        Python package — the pipeline engine (import as `occ.*`)
  scripts/        runnable entry points (calibration, trajectories, tests)
  tests/          synthetic ground-truth tests
  calibration/    calibration inputs/outputs (profiles reused every session)
  data/           raw videos + extracted frames        (git-ignored)
  results/        trajectories, plots, CSVs             (git-ignored)
matlab/           plot_trajectory.m + example CSV (results viewer)
slides/           advisor presentation (pptx + build script)
```

## The `occ` package (engine)
| Module | Responsibility |
|---|---|
| `calibration.py` | ChArUco board spec, board image generation, corner detection, **intrinsic** calibration (with outlier rejection). `BoardSpec.from_measured_json`. |
| `stereo.py` | **Stereo extrinsics** (`CALIB_FIX_INTRINSIC`) — relative camera pose from board pairs. `StereoExtrinsics` (R, t, save/load). |
| `reconstruct.py` | **Triangulation** — `triangulate_stereo` (pair) and `triangulate_nview` (DLT, for a 3rd camera). Projection matrices, reprojection error. |
| `accuracy_check.py` | **Rod/wand validation** — reconstruct known-length object, report mm error by axis. |
| `tracking.py` | **Coloured-marker detection & tracking** — HSV ranges (`COLOR_RANGES`), blob detection, `detect_wand` (2 red + 2 teal cluster), `detect_foot` (green toe + red heel, skin-rejected), `track_markers`. |
| `filtering.py` | **Trajectory cleaning** — velocity outlier rejection, gap-fill, Butterworth low-pass, `clean_trajectory`. |
| `worldframe.py` | **World-frame transform** — floor board → camera→world rigid transform (Z = height). `WorldTransform` (apply/save/load), Kabsch. |

## Scripts (run from `code/`)
**Calibration**
- `make_calib_board.py` / `make_big_calib_board.py` — generate printable ChArUco boards (small / big tiled).
- `extract_calib_frames.py` — pull sharp, pose-diverse frames from a board video.
- `run_intrinsics.py` — calibrate one camera → `calibration/intrinsics_<cam>.npz`.
- `check_calib_stability.py` — split-half focal-length stability test.
- `detect_board_holds.py` — find still-board segments in a video.
- `run_stereo_ransac.py` — **extrinsics** by geometric (time-free) hold matching (the one that worked).
- `run_stereo.py`, `solve_stereo_robust.py`, `diag_stereo.py` — earlier/diagnostic stereo paths.

**Validation & world frame**
- `run_rod_test.py` — rod/wand accuracy check → mm error.
- `compute_worldframe.py` — build the world transform from a floor clip; convert a trajectory CSV to world coords.

**Trajectories**
- `build_wand_trajectory.py` — moving-wand trajectory (validation of the moving chain).
- `build_foot_trajectory.py` — foot trajectory: track green/red → sync → triangulate → rigid-pair filter → world frame → CSV + plot.

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
