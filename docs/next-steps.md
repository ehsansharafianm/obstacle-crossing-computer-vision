# Next Steps — Roadmap

Living checklist of what's next, from the current state onward. Each stage marks
**[You]** (physical lab work) vs **[Code]** (I build/run it). See
[[camera-imu-workflow]] for the full design and [[open-items]] for decisions.

## Where we are  (see [[progress-log]] + [[2026-09-02]] for the full story)
- ✅ **First accuracy validation (rigid wand, test21):** precision ~2–6 mm std, but a
  systematic **~6 % scale underestimate** → likely the calibration board square size.
  Report/plots in `results/validation/test21/`; tool `matlab/plot_validation.m`.
- ✅ **Repo reorg** (videos/ raw + results/ generated) and **robustness pass** — detection
  hardened against scene/wardrobe colour clashes (cone, shirt, shorts) found in test18–20.
- 🔜 **NEXT: fix the ~6 % scale** — re-measure the calibration board squares with calipers;
  if ≠ 62.9 mm, update `results/calibration/active/board_measured_large.json`, re-run
  `build_calibration 17`, and re-shoot the wand (test) to confirm error drops to a few mm.

### Earlier state  (2026-08-29)
- ✅ **3× Pixel-8 rig** (ultrawide 60 fps): per-phone intrinsics, one-command 3-camera
  calibration (calib10: cam1↔cam2 0.71 px, floor 0.52 mm, cam2↔cam3 0.97 px).
- ✅ **Robust clap sync for all 3 cameras** — rigid-shoe-arbitrated + clap-seeded, and the
  clap now WINS when the rigid minimum aliases one stride away (fixed cam3 in test14).
- ✅ **n-view 3D + world frame** — cam1+cam2 precision core (widest baseline), cam3 gap-fill.
  test14: **L 15 mm / R 13 mm** toe-heel std over ~15 crossings, full lift/landing arcs.
- ✅ **Obstacle capture works at multiple heights** — reds detected by hue+shape (round-blob
  gate rejects skin/poles), reconstructed n-view from any 2 cameras. test14: **75 %
  coverage, 4 configs resolved with sub-mm scatter**. Reported as obstacle1/obstacle2 per time.
- ✅ Output time **zeroed at the clap**; **aligned review clips** auto-generated; MATLAB
  viewer shows trajectory (obstacle as scatter) + all-3-camera clap sync; processing-time log.
- ⚙️ **Clearance metric** is the researcher's own step (foot vs obstacle markers, both in xlsx).

### Immediate scope (this phase)
- [ ] **Clearance computation** — per crossing, min gap between each foot marker and the
  obstacle top (red markers stay ON the obstacle → auto-measure each of 6 heights).
- [ ] Optional: velocity outlier filter (kill the last spike); marker-colour swap to
  unlock cam2/cam3 coverage (colours absent from the lab background).
- [ ] Run the **6-obstacle-height protocol** (cameras fixed; one session per height).

---

## Stage 2 — Stereo extrinsics (relative camera positions)  ✅ DONE
Result: 0.74 px stereo RMS, baseline 2.04 m. Key lessons: big tiled board +
cameras ~45-60° apart + **static (propped) board** at each pose + geometric
(time-free) hold matching (`run_stereo_ransac.py`). Cameras must not move now.

Figure out where the cameras sit relative to each other, so 2D → 3D works.

- [ ] **[Decide]** final camera count — 2 vs **3** (3 preferred; the synthetic
      test showed ~half the error and it rescues trail-limb occlusion). See [[open-items]].
- [ ] **[Decide]** origin & axis convention (e.g. origin at obstacle base,
      X = travel, Y = mediolateral, Z = vertical) → [[coordinate-frame]] (to write)
- [ ] **[You]** Place cameras on tripods in FINAL positions (sagittal + oblique,
      ~60-90° apart). Once placed, **do not move them** for the session.
- [ ] **[You]** Same locked settings (1x, 1080p/240, landscape, AE/AF locked).
- [ ] **[You]** Record both cameras together — see [[extrinsic-calibration-capture]]
      (hold the board STILL at ~15-20 poses across the shared volume; no sync needed).
- [ ] **[Code]** Run `occ.stereo` → relative pose (R, t); check baseline & stereo
      reprojection error. I'll write the runner + a frame-sync helper.

## Stage 3 — Rod accuracy check (first real mm number)
The "trusted measurement" evidence for using cameras as the primary source.

- [ ] **[You]** Build a rigid rod with two clear markers a KNOWN distance apart
      (measure with calipers). See [[calibration-accuracy-check]].
- [ ] **[You]** With both cameras fixed, film the rod at many positions and
      orientations across the volume — **including vertical** (Z is the weak axis).
- [ ] **[Code]** Run `occ.accuracy_check` → mean/RMS/max error in mm, by axis.
      Pass criterion: define an acceptable RMS up front (tie to smallest
      clearance difference the study must resolve).

## Stage 4 — Marker detection choice (foot + obstacle)
- [ ] **[Decide]** marker type: colour vs reflective+IR; size ~15-20 mm so they
      span >=15 px at 1080p (frame the crossing zone tightly). See [[open-items]].
- [ ] **[Code]** Build the marker detector (`occ.tracking`) + validate against
      manual digitizing on a frame subset.

## Stage 5 — Pilot capture (1 subject, a few crossings)
Shake out the whole chain before full collection.

- [ ] **[Decide]** total crossing count structure (per-obstacle vs total) — sizes
      the digitizing labor. See [[open-items]].
- [ ] **[You]** Record 1 pilot: continuous video (both/all cameras) + IMU, with
      start/end sync anchors, a few crossings over 1-2 obstacles.
- [ ] **[Code]** Run end-to-end: track → triangulate → filter → IMU-sync →
      compute the 3 metrics for the pilot crossings. Find the bottlenecks.

## Stage 6 — IMU integration (sync + gait events)
- [ ] **[Confirm]** DOT-Awinda mutual sync status. See [[open-items]].
- [ ] **[Code]** Parse IMU CSVs (60 Hz; cols Euler/FreeAcc/Gyr, `SampleTimeFine`
      clock), detect toe-off/heel-strike, align camera timeline to IMU via anchors,
      index each crossing.

## Stage 7 — Full data collection & processing
- [ ] Only after the pilot validates the pipeline and the labor estimate is sane.

---

## Immediate: what to do next
1. ✅ **Obstacle as per-time markers** — `build_multi_trajectory` reconstructs the two red
   obstacle markers per frame (obstacle1/obstacle2) in the 'markers' sheet, so the obstacle
   can be moved between crossings; the researcher computes clearance from these + the feet.
2. **[You]** Record the obstacle heights (cameras fixed = calib11 stays valid; reds on the
   obstacle top; clap at start). Heights can be one-per-session OR moved between crossings.
3. **[You/Code]** Compute clearance (researcher's own step) from foot vs obstacle markers.
4. **[Code, optional]** Velocity outlier filter on feet; marker-colour swap for cam2/cam3 coverage.
