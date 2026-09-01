# calibration/ — camera calibration (sessions + shared artifacts)

This folder holds everything about camera calibration:

- **Calibration sessions** — one subfolder per session: `calib01/`, `calib02/`, …
  (the counterpart to the test sessions in the sibling `sessions/` folder).
- **Shared reference + active calibration** — the loose files at the root of this
  folder (see below), used by every test.

## Run a calibration session

Recalibrate at the **start of each recording session** — consumer tripods drift,
so a fresh extrinsics + world calibration keeps the 3D honest. Then record all
that session's tests without moving the cameras.

1. Place + **lock** the cameras (tape the tripod feet). Don't move/zoom them again.
2. Drop four clips into `calibration/calibNN/`:

   | File | What | Length |
   |------|------|--------|
   | `cam1_ext`, `cam2_ext` | big ChArUco board held **STATIC** at ~15–20 poses (both cameras) | ~60–90 s |
   | `cam1_floor`, `cam2_floor` | same board **flat on the floor** | ~10 s |

3. Run it (from `code/`):
   ```
   run_calib 4
   ```
   (or `.venv\Scripts\python.exe scripts\build_calibration.py 4`). A bare number
   `4` → `calib04`. Check `calib04/calib_run.txt`: stereo **RMS < 1.5 px**, floor
   **residual < 3 mm**.

## What a `calibNN/` session folder holds

| File | What it is |
|------|-----------|
| `cam1_ext`, `cam2_ext`, `cam1_floor`, `cam2_floor` (`.MOV`) | input clips (not committed to git) |
| `stereo_extrinsics.npz`, `world_transform.npz` | this session's computed calibration |
| `calib_run.txt` | the numbers: stereo RMS, baseline, floor residual, camera height |

Running `run_calib` also **promotes** the session's `.npz` to this folder's root
(the *active* calibration), so every test recorded afterwards uses it.

## Shared / active files at the root of `calibration/`

| File | What it is |
|------|-----------|
| `intrinsics_cam1.npz`, `intrinsics_cam2.npz` | per-lens calibration (stable; not redone per session — depends on lens/zoom, not position) |
| `stereo_extrinsics.npz`, `world_transform.npz` | the **active** calibration the foot pipeline reads (a copy of the latest session's) |
| `board_measured*.json`, `capture_settings.json`, `rod_markers.json` | measured board specs + capture settings |
| `charuco_board.png`, `big_charuco_*.{png,pdf}` | printable calibration boards |

Intrinsics are **not** redone per session; keep the zoom at 1× and they stay valid.
