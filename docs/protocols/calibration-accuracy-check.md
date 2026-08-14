# Protocol — Calibration Accuracy Check

The "trusted measurement" evidence for using the cameras as a **primary**
source. Reconstruct a rigid object of known length through the full pipeline
and report error in mm. See [[camera-imu-workflow]] §8.

> Status: **draft — fill in the bracketed values once hardware is chosen.**

## Materials

- Rigid rod with two well-defined markers a **known** distance apart
  ([___] mm, measured with calipers)
- Same camera setup, calibration, and marker type as the real study

## Procedure

1. Calibrate cameras (checkerboard/wand) exactly as for a real session.
2. Place the rod at **multiple positions** spanning the capture volume:
   near/far, left/right/center, low/high.
3. At each position, record it in **multiple orientations**, including
   **vertical** — clearance is a Z-axis measurement, so Z accuracy matters most.
4. Target ≥ [___] positions × [___] orientations.
5. Run each through the full pipeline: detect markers → triangulate → 3D points.
6. For each sample, compute reconstructed rod length; error = reconstructed − true.

## Report

- Mean error (mm), RMS error (mm), max error (mm)
- Error broken out by axis (X / Y / **Z**) and by region of the volume
- Note any position/orientation where error spikes (informs camera placement)

## Pass criteria

- [ ] Define acceptable RMS threshold up front: [___] mm
      (tie to how small a clearance difference the study must resolve)
