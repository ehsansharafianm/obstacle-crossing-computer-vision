# calibrations/ — one folder per calibration session

Calibration **sessions** live here (`calib01`, `calib02`, …), right next to
`experiments/` (test sessions). Recalibrate at the **start of each recording
session** — consumer tripods drift, so a fresh extrinsics + world calibration
keeps the 3D honest. Then record all that session's tests without moving the
cameras.

> Not to be confused with the sibling **`calibration/`** folder (singular), which
> holds the shared reference artifacts — the per-lens intrinsics, board specs, and
> the *active* `.npz` files the pipeline reads. This folder holds the raw session
> clips and each session's computed copy.

## How to run a calibration session

1. Place + **lock** the cameras (tape the tripod feet). Do not move/zoom them
   again this session.
2. Drop four clips into `calibrations/calibNN/`:

   | File | What | Length |
   |------|------|--------|
   | `cam1_ext`, `cam2_ext` | big ChArUco board held **STATIC** at ~15–20 poses (both cameras) | ~60–90 s |
   | `cam1_floor`, `cam2_floor` | same board **flat on the floor** | ~10 s |

3. Run it (from `code/`):
   ```
   run_calib 4
   ```
   (or `.venv\Scripts\python.exe scripts\build_calibration.py 4`). A bare number
   `4` → `calib04`.

## What each session folder holds

| File | What it is |
|------|-----------|
| `cam1_ext.MOV`, `cam2_ext.MOV`, `cam1_floor.MOV`, `cam2_floor.MOV` | your input clips (not committed to git) |
| `stereo_extrinsics.npz`, `world_transform.npz` | this session's computed calibration |
| `calib_run.txt` | the numbers: stereo RMS, baseline, floor residual, camera height |

Running `run_calib` also **promotes** this session's `.npz` to the active
`calibration/` folder, so every test recorded afterwards (cameras unmoved) uses it.

## Notes
- **Intrinsics are not redone here** — they depend on the lens/zoom (kept at 1×),
  not camera position. They stay in `calibration/`.
- Good session: stereo **RMS < 1.5 px**, floor **residual < 3 mm**. If not,
  re-record (usually the board wasn't held still, or too few distinct poses).
