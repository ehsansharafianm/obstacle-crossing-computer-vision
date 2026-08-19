# Per-Session Protocol — Calibrate, then Record

The repeatable checklist for a recording day. Consumer tripods drift, so **each
session starts with a fresh extrinsics + world calibration**, then every crossing
is recorded with the cameras locked. See [[progress-log]] for context and
[[extrinsic-calibration-capture]] for the board-capture detail.

## The golden rule
> Once you calibrate, **do not move or zoom the cameras** for the rest of the
> session. If a camera moves — even a bump — the calibration is invalid and you
> must redo steps 2–3.

Intrinsics (per-lens) are **not** redone each session — they depend on the
lens/zoom, not position. Keep the zoom at **1×** and they stay valid.

---

## 0. Settings (both iPads, every clip)
- **1× lens, 1080p / 240 fps, landscape, AE/AF locked.**
- Same on both cameras. (fps doesn't matter for the static calibration board, but
  keeping settings constant avoids forgetting to reset them.)

## 1. Place + lock the cameras
- Two tripods — one sagittal (side), one oblique — both seeing the crossing zone
  with good overlap.
- **Tape the tripod feet to the floor, tighten everything**, sandbag if you can.

## 2. Record the 4 calibration clips → `calibration\sessions\calibNN\`
| Clip | What | Length |
|------|------|--------|
| `cam1_ext`, `cam2_ext` | big ChArUco board held **STATIC** at ~15–20 poses (vary distance, left/right, tilt); both cameras see it each time | ~60–90 s |
| `cam1_floor`, `cam2_floor` | same board lying **flat on the floor** in the crossing zone | ~10 s |

Static is critical — prop the board at each pose rather than hand-holding.

## 3. Build the calibration → one command
```
run_calib 4
```
Check `calibration\sessions\calib04\calib_run.txt`:
- stereo **RMS < 1.5 px**
- floor **residual < 3 mm**
- camera height ≈ your physical setup

If any is off, re-record step 2 (usually the board wasn't held still, or too few
distinct poses). This promotes the new calibration to active — all tests below use it.

## 4. Record each crossing → `experiments\testNN\`
**Do not touch the cameras.** For each test:
- **Clap once**, sharp, at the start (this is the camera sync — mandatory).
- **2–3 slow, deliberate crossings**, foot staying in **both** camera views.
- Markers: **rounded** green (toe) + red (heel), **red on the back of the heel**,
  closed sneaker, marked side facing the cameras. Bright, even lighting.
- Save the two clips into the folder as `cam1` / `cam2`.

## 5. Process → one command per test
```
run_test 5
```
Read `experiments\test05\test05_run.txt`. Good signs: detection > ~85 % while the
foot is in view, **toe–heel std < ~15 mm**.

---

## Quick reference
| Step | Folder | Command |
|------|--------|---------|
| Calibrate (once per session) | `calibration\sessions\calibNN\` ← 4 clips | `run_calib N` |
| Each crossing | `experiments\testNN\` ← 2 clips (`cam1`,`cam2`) | `run_test N` |

A bare number works everywhere (`4` → `calib04` / `test04`). Both `run_*.bat`
files can also be double-clicked — they'll ask for the number.
