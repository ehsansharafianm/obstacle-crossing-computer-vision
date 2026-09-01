# sessions/ — one folder per test

Each test/crossing lives in its own folder, `testNN`. Everything about that
test (the two input videos and every output) stays together. (Calibration
sessions are the sibling `calibration/calibNN/` folders — see `calibration/README.md`.)

## How to run a test

1. **Make/record** the test. Copy the two iPad clips into a folder named after
   the test, renamed `cam1` and `cam2`:

   ```
   sessions/test01/cam1.MOV
   sessions/test01/cam2.MOV
   ```

   (Don't have the folder yet? Just run step 2 with a new id — it creates the
   folder and tells you to drop the videos in.)

2. **Process** it with one command (run from `code/`):

   ```bash
   run_test 1
   ```

   (or `.venv\Scripts\python.exe scripts\build_foot_trajectory.py test01`).
   A bare number `1` → `test01`.

3. **View** it in MATLAB (from the `matlab/` folder):

   ```matlab
   plot_trajectory('test01')
   ```

## What each test folder contains

| File | What it is |
|------|-----------|
| `cam1.MOV`, `cam2.MOV`   | your two input clips (not committed to git) |
| `testNN_trajectory.csv`  | the result: `time_s, toe_xyz_mm, heel_xyz_mm` (world frame, Z = height) |
| `testNN_trajectory.png`  | quick-look plot (toe/heel height + toe–heel distance) |
| `testNN_run.txt`         | the run's numbers: coverage %, sync offset, toe–heel mean/std, frames kept/dropped |

## Notes

- The **videos are git-ignored** (they're large); the small CSV/PNG/run.txt are
  kept so each test's result is versioned.
- The **active calibration** (`calibration/*.npz`) is shared across all tests in a
  session — do **not** move the cameras, or re-run `run_calib` first (see
  `calibration/README.md`).
- Naming is up to you: `test01`, `P03_obstacle2`, `pilot_clap` all work — the id
  becomes the folder name and the prefix on every output file.
