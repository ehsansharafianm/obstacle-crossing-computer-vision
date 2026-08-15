# Next Steps — Roadmap

Living checklist of what's next, from the current state onward. Each stage marks
**[You]** (physical lab work) vs **[Code]** (I build/run it). See
[[camera-imu-workflow]] for the full design and [[open-items]] for decisions.

## Where we are
- ✅ Board printed & measured (square = 28.523 mm)
- ✅ cam1 & cam2 **intrinsic** calibration — STABLE, saved to
  `code/calibration/intrinsics_cam{1,2}.npz`
- ✅ Geometry + accuracy-check code written and synthetic-validated
- ✅ Pushed to GitHub (`main`)

---

## Stage 2 — Stereo extrinsics (relative camera positions)  ← NEXT
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
1. Decide **2 vs 3 cameras** (leaning 3) and the **origin/axes** convention.
2. Prepare the **accuracy-check rod** (rigid, 2 markers, measured length).
3. When set up in the lab: record the **Stage 2 extrinsics** video.
