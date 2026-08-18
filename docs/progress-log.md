# Progress Log — Achievements & Steps

What we've built and proven, in order. See [[code-structure]] for the code,
[[next-steps]] for what's left, [[automated-pipeline]] for the system plan.

## Headline achievements
- **Two consumer iPads → a validated ~2 mm 3D motion-capture system.**
- Full chain proven end-to-end: **calibration → tracking → sync → 3D → world-frame height**.
- The hardest technical risk (mm-accuracy from consumer cameras) is **retired**.

## The journey, step by step

### 1. Environment & scaffolding
- Repo split: `code/` (pipeline, data, results) + `docs/` (this Obsidian vault).
- Python 3.14 + OpenCV **5.0** (contrib), numpy/scipy/pandas/matplotlib. `occ` package.
- Capture locked: **1080p / 240 fps, 1x lens, landscape, AE/AF locked**.

### 2. Intrinsic calibration (per iPad)  ✅
- ChArUco board; printed and measured (**square = 28.523 mm**; print scaled ~95%).
- Validated by a **split-half focal-length test** — both cameras STABLE (0.0%), ~0.9 px RMS.
- **Hard-won lesson:** stability needs a **big board, held at ~constant distance, with heavy tilt**;
  low reprojection error alone is misleading. Took ~4 reshoots to learn.
  See [[intrinsic-calibration-capture]] and the [[occ-intrinsic-calibration-technique]] memory.

### 3. Stereo extrinsics (camera pair geometry)  ✅
- **0.74 px** RMS, baseline **2.04 m**.
- Required: a **big tiled board** (57 cm, 6 Letter pages), cameras **~45-60° apart at equal height**,
  the board held **static (propped)** at each pose, and **geometric (time-free) matching**
  (`run_stereo_ransac.py`) — plain stereoCalibrate + motion/hand-held drift failed.
  See [[extrinsic-calibration-capture]].

### 4. Accuracy validation (rod / wand test)  ✅
- Reconstructed a rigid wand (4 coloured markers, known distances) → **~2 mm**
  (best-half poses 2.1 mm; 3.9 mm overall, inflated by hand-held drift + crumpled markers).
- This is the "trusted measurement" evidence. See [[calibration-accuracy-check]].

### 5. Marker tracking & camera sync  ✅
- Colour-marker detection (`occ.tracking`): red / green / teal, blob + HSV, with clutter
  rejection (skin, blue floor tape) via proximity rules.
- Camera-to-camera **sync without hardware**: self-consistency — find the time offset that
  makes a rigid object's known/constant distances hold (works where motion cross-correlation failed).

### 6. Moving 3D trajectory  ✅
- Validated on the wand in motion: rigid distances stay flat at the known values through
  the movement → tracking + sync + triangulation all work together on moving markers.
- **iPad fps gremlin resolved:** one iPad kept recording 30 fps; fixed so both are true 240 fps.

### 7. World-frame transform (real height)  ✅
- `occ.worldframe`: board flat on floor → rigid transform camera-frame → **world frame**
  (Z = up, floor = Z 0, X/Y in floor plane).
- Validated: floor-flatness residual **0.47 mm**, computed **camera height 1011 mm** (matches the
  ~100 cm physical setup). Rigid transform → the ~2 mm accuracy is preserved.

### 8. Foot pilot (green toe + red heel)  ⚙️ in progress
- End-to-end on a real foot: detect → track → sync → triangulate → **world-frame height** → CSV.
- Added **rigid-pair outlier rejection** (drop frames whose toe-heel distance is an outlier).
- **Bigger markers** (colored plastic) markedly improved detection.
- Remaining quality work is recording-side: bigger/rounder markers, a **clap** for precise sync,
  and slower controlled motion → smooth, physically-sane height curves.

## Deliverables produced
- **MATLAB viewer** `matlab/plot_trajectory.m` — 3D + X/Y/Z-vs-time, per-marker toggles,
  Line/Scatter switch; auto-detects markers from any pipeline CSV.
- **Advisor deck** `slides/obstacle_crossing_update.pptx` (5 slides).
- CSV trajectory outputs (`results/*_trajectory*.csv`), world-frame and camera-frame.

## Scope decision (2026-08-18)
Focus for now: **trajectories + XYZ/time output + occlusion handling**. IMU sync and
clearance-metric computation are deferred (handled separately by the researcher).
