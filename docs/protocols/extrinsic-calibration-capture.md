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
**Both cameras must see the PRINTED pattern at the same time.** The board has the
pattern on one side only — aim that side at the **midpoint between the two
cameras**, never straight at one camera (the other then sees the blank back and
detects nothing). At each pose ask: "can BOTH cameras see the checkerboard now?"
*(First attempt failed here: the pattern faced cam1, so cam2 detected the board
in 0 frames.)*

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

## Remember
- Redo THIS capture whenever cameras move; intrinsics stay valid (don't redo those).
- After extrinsics, cameras must stay put through the crossing recordings.
