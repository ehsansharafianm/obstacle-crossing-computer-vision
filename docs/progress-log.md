# Progress Log — Achievements & Steps

What we've built and proven, in order. See [[code-structure]] for the code,
[[next-steps]] for what's left, [[automated-pipeline]] for the system plan.

## Headline achievements
- **First accuracy validation — rigid wand** (2026-09-02, test21): precision **~2–6 mm
  std** (sub-2 %), but a systematic **~6 % scale underestimate** → calibration board
  square size. Precise now; accurate once the board size is corrected. See [[2026-09-02]].
- **Repo reorg + robustness pass** (2026-09-02): split **videos/ (raw) + results/
  (generated)**; hardened detection against scene/wardrobe colour clashes (cone→obstacle,
  shirt→R_toe, shorts→R_heel), all found via real sessions test18–20.
- **Multi-height obstacle capture works** (2026-08-29). test14 (4 configs): obstacle
  reconstructed in **75 %** of frames, all four windows resolved with sub-mm scatter, feet
  **15 / 13 mm** toe-heel std — after fixing orange-red marker detection (hue + round-blob
  shape gate), n-view obstacle triangulation, and clap-over-alias sync. See [[2026-08-29]].
- **THREE Google Pixel 8 phones → a working 3-camera clearance-measurement system**
  (2026-08-28). Ultrawide 60 fps, all 3 cameras clap-synced, n-view 3D. test10:
  **L 16 mm / R 12 mm** toe-heel std with full lift/landing coverage. See [[2026-08-28]].
- **Two consumer iPads → a validated ~2 mm 3D motion-capture system** (earlier phase).
- **Clean 3D foot-clearance trajectory on a real crossing** (test06): clearance arcs +
  17 mm rigid-shoe consistency. The full chain works: calibrate → clap → track → 3D → clearance.
- **Bilateral capture** (test07): both feet + 2 ground markers tracked at once
  (`build_multi_trajectory.py`); left foot **14 mm** toe–heel std.
- Turnkey per-session workflow: `run_calib N` / `run_test N` / `build_multi_trajectory N`.
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

### 10. Migration to a 3× Pixel-8 rig  ✅ (2026-08-28, [[2026-08-28]])
- **Per-phone intrinsics** for cam1/cam2/cam3 (stabilization OFF is critical — EIS shifts
  the principal point ~110 px). Recording mode **auto-detected** (normal 60 fps vs ¼ slow-mo).
- **3-camera calibration in one command** (`build_calibration N`): cam1↔cam2 + floor +
  cam2↔cam3 (cam2 = hub); board-hold cap stops the matcher exploding on long clips. It also
  now **reports the +X/+Y axis directions** (set by the floor-board placement).
- **Robust clap sync** (`occ.audiosync` + `build_multi_trajectory`): rigid-shoe-arbitrated,
  **clap-seeded** — survives quiet claps and cameras that start many seconds apart (found a
  +13.7 s cam3 offset). All three cameras synced; the audio figure/sheet cover all three.
- **n-view reconstruction**: cam1+cam2 is the precision core (**widest baseline** wins over
  cam2↔cam3's lower RMS); cam3 gap-fills. Output **time zeroed at the clap**; pre-clap trimmed.
- **Aligned review clips** auto-written to `sessions/<id>/synced_videos/` (`sync_cut.py`).

### 11. Ultrawide FOV to fill lift/landing  ✅ (2026-08-28)
- Space-constrained, so widened FOV via **normal 60 fps + ~0.6-0.7× ultrawide** (rather than
  moving cameras back). Re-shot intrinsics per phone; the standard distortion model fits
  (~94° HFOV, RMS 0.35-0.42 px). calib10: cam1↔cam2 0.71 px, floor 0.52 mm, cam2↔cam3 0.97 px.
- test10: **L 16 mm / R 12 mm**, full arcs, all 3 cameras contributing.
- **Coverage bottleneck** stays: cam2/cam3 detect ~29 % (vs cam1 59 %); the safe fix is
  marker colours absent from the lab background (single-marker keeping otherwise grabs clutter).

### 12. Multi-height obstacle capture works  ✅ (2026-08-29, [[2026-08-29]])
- Ran two multi-height sessions (test13: 2 heights, test14: **4 configs, 5 min, ~15 crossings**).
  The obstacle is now reported as **per-time markers** `obstacle1`/`obstacle2` (X/Y/Z), so it
  can be moved between crossings; the researcher computes clearance from these + the feet.
- **test14: obstacle coverage 6 % → 75 %**, all four configs resolved with **sub-mm scatter**
  (two height levels ~180 mm and ~345 mm; the two reds are the board's two ends at X = ±281 mm,
  Y ≈ 0 — matches the board-along-X / walk-along-Y layout). Feet **15 / 13 mm** toe-heel std.
- Three fixes got there (see [[2026-08-29]]):
  1. **Obstacle detection was the real bottleneck.** The reds are **orange-red (hue ≈ 3–9)**,
     but the detector used hue 172–180 only → it missed them across whole time-windows.
     Widening naively then grabbed the subject's **bare legs** and the **orange poles**
     (same hue). Fix (`occ.tracking`): hue **0–12 + 170–180** with a saturation floor (upper
     bound 12 stays below the poles at ≥16) **plus a round-blob shape gate** (circularity ≥ 0.55,
     bbox fill ≥ 0.6) — the balls pass (circ 0.8–0.9), legs/equipment (circ ~0.2) are rejected.
  2. **Obstacle reconstructed n-view from any 2 of 3 cameras** (`match_reds_nview`), like the feet.
  3. **Clap wins over gait-alias sync.** When the rigid-shoe offset disagrees with the clap by
     >1 s (a false minimum one stride away) the clap is trusted unless its own fit is much worse.
     Fixed cam3 (+5.74 → +7.66 s); **R-foot outliers 1001 → 88**.
- Also from test13: obstacle **reproj-error gate** (~28 px) + **2-pass MAD rolling-median** filter
  to kill occlusion spikes.
- **Note for the 6-height protocol:** detection works, but the orange-red balls *share* the
  scene's hue (skin + poles) — the shape gate does the heavy lifting. A marker colour absent
  from the room (e.g. blue; feet already use purple/green/teal/pink) would make it bulletproof.

### 13. Repo reorg + real-session robustness  ✅ (2026-09-02, [[2026-09-02]])
- **Layout split**: raw video → `videos/{sessions,calibration}/`; everything generated →
  `results/{sessions, calibration/active, calibration/<id>}/`. `occ/paths.py` anchors all
  paths to the repo root. Scripts, `.bat`s, MATLAB viewers, `.gitignore`, docs updated.
- **calib16** (gait mat on floor): floor step fixed with a **multi-scale board detector**
  (upscales a small/distant floor board). **calib17** (cameras moved): floor 0.47 mm.
- **Detection hardened against scene/wardrobe colour clashes**, each found in a real session:
  obstacle **plausibility gate** (kills triangulation blow-ups); obstacle **best-pair matcher**
  (cam1's orange **cone** false-red → obstacle 2 %→51 %); **teal range tightened** (grey-green
  **shorts** → R_heel offset 329→111 mm, std 37→10 mm); patterned **shirt** → neutral clothing.
- **Synced clips start AT the clap**; `plot_trajectory` marker-matched colours + toggles on
  both figures; **live progress %+ETA**.

### 14. First accuracy validation — rigid wand  ✅ (2026-09-02, test21)
- Four foot markers on a rigid T-wand moved through the volume; distances vs known geometry.
- **Precision excellent (~2–6 mm std, ~1–2 %)** — highly repeatable across the space.
- **Accuracy: systematic ~6 % underestimate**, error proportional to distance = a **scale
  error** (mean ratio ≈ 0.94). Most likely the **calibration board square size**
  (62.9 mm assumed; ~66–67 mm real gives ≈0.944). Report + plots in
  `results/validation/test21/`; new tool `matlab/plot_validation.m`.
- **Action:** re-measure board squares, update `board_measured_large.json`, re-run
  `build_calibration 17`, re-shoot the wand to confirm.

## Deliverables produced
- **MATLAB viewer** `matlab/plot_trajectory.m` — 3D + X/Y/Z-vs-time, per-marker toggles,
  Line/Scatter switch; auto-detects markers from any pipeline CSV.
- **Advisor deck** `slides/obstacle_crossing_update.pptx` (5 slides).
- CSV trajectory outputs (`results/*_trajectory*.csv`), world-frame and camera-frame.

## Scope decision (2026-08-18)
Focus for now: **trajectories + XYZ/time output + occlusion handling**. IMU sync and
clearance-metric computation are deferred (handled separately by the researcher).
