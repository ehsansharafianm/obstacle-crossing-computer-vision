# Progress Log — Achievements & Steps

What we've built and proven, in order. See [[code-structure]] for the code,
[[next-steps]] for what's left, [[automated-pipeline]] for the system plan.

## Headline achievements
- **Two consumer iPads → a validated ~2 mm 3D motion-capture system.**
- **Clean 3D foot-clearance trajectory on a real crossing** (test06): clearance arcs +
  17 mm rigid-shoe consistency. The full chain works: calibrate → clap → track → 3D → clearance.
- **Bilateral capture** (test07): both feet + 2 ground markers tracked at once
  (`build_multi_trajectory.py`); left foot **14 mm** toe–heel std.
- Turnkey per-session workflow: `run_calib N` / `run_test N` → CSV + plot.
- The hardest technical risks (mm-accuracy from consumer cameras; clean foot tracking) are **retired**.

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

### 8. Foot clearance trajectory (purple toe + green heel)  ✅ WORKS (test06, 2026-08-19)
- End-to-end on a real foot: detect → track → **clap-sync** → triangulate → **world-frame height** → CSV.
- **Clean result:** clear clearance arcs (toe/heel rise ~300–500 mm over each crossing,
  ~60 mm baseline) and a **17 mm** toe–heel rigid-shoe std (= shoe length, 294 mm).
- The three fixes that got there (see [[2026-08-19]] and [[foot-marker-recording-protocol]]):
  1. **Spherical, uniquely-coloured markers** — purple toe + green heel (red failed:
     the maroon couch + box label are also red → false heels).
  2. **Cameras moved closer** → markers big in frame → the fast-crossing 2D jitter collapses
     (toe–heel std 67 → 17 mm). Move ≠ zoom; recalibrate after moving.
  3. **One-clap audio sync** (`occ/audiosync.py`, peak-based) — cam sync to the ms, off-frame.
- Cleaning: **plausibility gate** (drop impossible 3D) + rigid-pair outlier rejection;
  honest empty gaps where the foot is out of both views.
- Remaining: **coverage** (~50%, raise with continuous crossings) and occlusion (3rd camera later).

### 9. Systematic per-session pipeline  ✅
- `run_calib N` (calibration session, [[session-workflow]]) and `run_test N` (foot test) —
  drop clips in a folder, one command → CSV + plot + run log. Calibration is validated
  per session (calib06: 0.92 px, floor 0.65 mm, camera height 986 mm).

## Deliverables produced
- **MATLAB viewer** `matlab/plot_trajectory.m` — 3D + X/Y/Z-vs-time, per-marker toggles,
  Line/Scatter switch; auto-detects markers from any pipeline CSV.
- **Advisor deck** `slides/obstacle_crossing_update.pptx` (5 slides).
- CSV trajectory outputs (`results/*_trajectory*.csv`), world-frame and camera-frame.

## Scope decision (2026-08-18)
Focus for now: **trajectories + XYZ/time output + occlusion handling**. IMU sync and
clearance-metric computation are deferred (handled separately by the researcher).
