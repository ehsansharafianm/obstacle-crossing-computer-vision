# Next Steps — Roadmap

Living checklist of what's next, from the current state onward. Each stage marks
**[You]** (physical lab work) vs **[Code]** (I build/run it). See
[[camera-imu-workflow]] for the full design and [[open-items]] for decisions.

## Where we are  (see [[progress-log]] + [[2026-08-28]] for the full story)
- ✅ **3× Pixel-8 rig** (ultrawide 60 fps): per-phone intrinsics, one-command 3-camera
  calibration (calib10: cam1↔cam2 0.71 px, floor 0.52 mm, cam2↔cam3 0.97 px).
- ✅ **Robust clap sync for all 3 cameras** (rigid-shoe-arbitrated, clap-seeded) — survives
  quiet claps + far-apart start times.
- ✅ **n-view 3D + world frame** — cam1+cam2 precision core (widest baseline), cam3 gap-fill.
  test10: **L 16 mm / R 12 mm** toe-heel std, full lift/landing arcs.
- ✅ Output time **zeroed at the clap**; **aligned review clips** auto-generated; **axis
  readout + flip** tool; MATLAB viewer shows trajectory + all-3-camera clap sync.
- ⚙️ **Clearance metric** not yet computed (next); coverage limited by cam2/cam3 detection.

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
1. **[Code]** Add the **clearance computation** to `build_multi_trajectory` (foot vs
   obstacle-top red markers, per crossing, per foot).
2. **[You]** Record the **6 obstacle heights** (cameras fixed = calib10 stays valid; reds on
   the obstacle top; clap at start; one session per height → `test11`, `test12`, ...).
3. **[Code, optional]** Velocity outlier filter; marker-colour swap to raise cam2/cam3 coverage.
