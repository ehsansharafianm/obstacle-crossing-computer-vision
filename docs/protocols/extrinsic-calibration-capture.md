# Protocol — Stereo Extrinsics Capture (both cameras together)

Finds where the cameras sit **relative to each other**, so 2D → 3D triangulation
works. Uses the already-locked intrinsics ([[intrinsic-calibration-capture]]) and
solves only the relative pose. See [[camera-imu-workflow]], [[next-steps]].

> **The no-sync trick:** hold the board STILL at each pose. While it's stationary,
> a frame from cam1 and a frame from cam2 show the *same* board position even if
> the cameras aren't frame-synced — so we don't need hardware sync or a perfect
> clap. Just hold still ~2 s per pose.

## Before you start
- **Cameras in FINAL positions** on tripods (sagittal + oblique, ~60-90° apart),
  aimed at the crossing zone. **Once placed, do not move them** — not for the
  extrinsics, and not through the crossing recordings that follow. If a camera is
  bumped, redo this capture.
- Same locked settings as always: **1x, 1080p/240, landscape, AE/AF locked.**
- Intrinsics don't change here; camera *position* is what we're capturing.

## #1 rule (the mistake to avoid)
**Both cameras must see the PRINTED pattern at the same time**, and the cameras
are LOW (near floor), so:
- Hold the board **UPRIGHT** (pattern facing sideways/horizontally, like a sign),
  **not** flat on top of a box facing the ceiling — a ceiling-facing pattern is
  edge-on to low cameras and detects nothing.
- Aim the pattern at the **midpoint between the two cameras** so both see its
  face (never straight at one camera → the other sees the blank back).
- **Verify before recording:** hold one pose and look at BOTH iPad screens — can
  you see the checkerboard on both? If not, rotate until you can, then record.

*Failures so far: attempt 1 — pattern faced only cam1 (cam2 = 0 detections);
attempt 2 — pattern lay flat facing the ceiling, edge-on to both (0 detections
on both). Fix: upright, facing horizontally toward the midpoint of the cameras.*

## What makes a good extrinsics capture
The board must be seen by **BOTH cameras at the same time** (see #1 rule above),
moved through the **shared volume where the crossing actually happens**:
- **Overlap only** — keep the board where both cameras can see it (the crossing zone).
- **Fill the 3D volume** — near/far (along travel), left/right (mediolateral), and
  **low to obstacle-height (vary Z)**. Z is the weak axis, so cover height well.
- **Tilt** the board at each pose (angled, not flat).
- Board **large enough to detect** in both views but fully visible to both.

## Procedure
1. Start **both** cameras recording (roughly together — exact timing not critical).
2. Do a **shared start cue**: one clap or hand-wave in view of both cameras (helps
   line up the two timelines).
3. Move the board through **~15-20 poses** spanning the shared volume. At each:
   - hold it **STILL ~2 s**, **tilted**, visible to both cameras,
   - then move to the next pose (near/far, left/right, low/high).
4. Do the shared cue again at the end (optional, helps confirm alignment).
5. Stop both recordings.
6. Save as `code/data/cam1_extrinsics.MOV` and `code/data/cam2_extrinsics.MOV`.

## Then (Code)
Run the stereo runner (to be built) → relative pose (R, t). Checks:
- **Baseline** (distance between cameras) matches your physical setup.
- **Stereo reprojection error** is low (< ~1 px).
Then triangulation is live and we can do the [[calibration-accuracy-check]] rod test.

## Lessons from failed attempts (do these)
- **Big board** (57 cm tiled) — small A4 was undetectable at room distance. ✅ solved.
- **Cameras ~45-60° apart, SAME height** — a wide (~3.6 m baseline) setup made
  one camera's view too oblique to detect the board; only 5 poses were seen by
  both, and they disagreed by ~40°. Closer convergence lets BOTH cameras see the
  board well at every pose. Widen later once the pipeline is validated.
- **15-20 poses, held still ~4 s each** — need many moments where BOTH cameras
  see the board still simultaneously (matching is what stereo needs).
- **Verify on BOTH screens** at each pose before holding — the previously-weak
  camera must clearly see the checkerboard too.
- Ruled out as causes (so don't chase them): intrinsics (sub-pixel), board
  flatness (per-view PnP 0.4 px), time sync (swept all offsets).

## Code
`scripts/run_stereo.py` (auto-sync + hold matching + stereoCalibrate) and
`scripts/solve_stereo_robust.py` (offset sweep + planar-ambiguity consensus).
Need ~>=8 consistent simultaneous still holds for a trustworthy result.

## Remember
- Redo THIS capture whenever cameras move; intrinsics stay valid (don't redo those).
- After extrinsics, cameras must stay put through the crossing recordings.
