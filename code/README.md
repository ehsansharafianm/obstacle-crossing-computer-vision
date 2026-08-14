# code/ — Obstacle-crossing pipeline

Python pipeline that turns multi-camera video + IMU exports into per-crossing
spatial metrics. Design rationale lives in the Obsidian vault at `../docs/`.

## Layout

```
code/
  src/occ/        Python package (one module per pipeline stage)
  data/           Raw footage & IMU exports          (git-ignored)
  calibration/    Calibration inputs/outputs         (large files git-ignored)
  results/        Computed metrics & figures         (git-ignored)
  requirements.txt
```

## Pipeline stages (status)

| # | Stage                     | Module                  | Status |
|---|---------------------------|-------------------------|--------|
| 1a| Intrinsic calibration     | `occ.calibration`       | ✅ cam1 & cam2 STABLE (0.0% split-half, ~0.93px RMS) |
| 1b| Stereo extrinsics         | `occ.stereo`            | ☐ needs both cams set up together |
| 2 | Calibration accuracy check| `occ.accuracy_check`    | ✅ rod test + report (synthetic-validated) |
| 3 | Obstacle digitizing       | `occ.digitize_obstacle` | ☐ todo |
| 4 | Foot-marker tracking      | `occ.tracking`          | ☐ todo |
| 5 | 3D reconstruction         | `occ.reconstruct`       | ✅ stereo + N-view (synthetic-validated) |
| 6 | Filtering                 | `occ.filtering`         | ☐ todo |
| 7 | IMU sync alignment        | `occ.sync`              | ☐ todo |
| 8 | Metric computation        | `occ.metrics`           | ☐ todo |

Start with stages 1–2: they gate everything downstream and can be built and
validated before full experimental capture — only a checkerboard and a
known-length rod are needed.

## Setup

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
pip install -r requirements.txt
```
