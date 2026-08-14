# Protocol — Intrinsic Calibration Capture (per iPad)

One video per camera of the printed ChArUco board, filmed in the LOCKED capture
mode. Goal: a *well-constrained* lens estimate. See [[camera-imu-workflow]].

> A calibration can have low reprojection error and still be WRONG if the board
> didn't cover the frame or wasn't tilted. Verify with the stability check
> (`code/scripts/check_calib_stability.py`) — the two halves' focal length must
> agree within ~2%.

## Settings (must match the experiment)
- 1080p, 240 fps, **1x lens**, **landscape**
- **AE/AF locked** (press-and-hold until the yellow "AE/AF LOCK" banner)

## Setup that guarantees sharp frames
- Put the **iPad on a tripod** (steady). You hold the board and move it — a
  still camera means no motion blur.

## The things that make or break it
1. **BIG board** — hold it CLOSE so it fills roughly **half to most of the
   frame**. A small/far board (tiny in frame) localizes poorly and gives an
   unstable focal length. (Past failures had the board only ~10% of frame width.)
2. **CONSTANT distance** — keep the board at ~one distance the whole video. Do
   NOT go "close then far": with focus locked, changing distance shifts the
   effective focal length across the recording and ruins the calibration.
3. **TILT hard** — at every pose angle the board **30-45°** (top-away,
   bottom-away, left-away, right-away). NEVER flat to the camera. Tilt (not
   distance) is what pins down focal length.
4. **COVER the frame** — move the (big, tilted) board so its pattern reaches all
   four **corners** and **edges** and the **bottom**. Partial views are fine —
   ChArUco reads whatever markers are visible.
5. **VERIFY the focus lock held** — with AE/AF locked at your working distance,
   the board should look sharp there. If it stays razor-sharp even when you move
   it much closer/farther, the lock is NOT holding (AF is tracking) — re-lock.

## Procedure (~60 s, like taking ~15 deliberate photos at one distance)
Stand at a fixed spot; keep the board at ~arm's length so it's LARGE in frame.
Pause ~1-2 s at each pose (pausing kills blur):
- 4 corners (board tilted, its edge pushed into each corner)
- 4 edge-midpoints (top, bottom, left, right)
- center a few times, each with a different strong tilt
- keep the distance the SAME throughout

## Verify before trusting
```
.venv\Scripts\python.exe scripts\extract_calib_frames.py data\cam1_board.MOV data\intrinsics_cam1 --candidates 3000
.venv\Scripts\python.exe scripts\check_calib_stability.py data\intrinsics_cam1
```
- Want: **coverage >= ~18/24 cells** and **fx halves agree within 2%** (STABLE).
- If UNSTABLE: more tilt, more corner/edge coverage, more distance variation.

## History
- 2026-08-14: first attempts UNSTABLE (cam1 6%, cam2 38%) — board was moved
  around but held mostly flat and never reached frame corners/bottom. Re-shot
  with deliberate tilt + full-frame coverage.
