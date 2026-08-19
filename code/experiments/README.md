# experiments/ — one folder per test

Each test/crossing lives in its own folder, `testNN`. Everything about that
test (the two input videos and every output) stays together.

## How to run a test

1. **Make/record** the test. Copy the two iPad clips into a folder named after
   the test, renamed `cam1` and `cam2`:

   ```
   experiments/test01/cam1.MOV
   experiments/test01/cam2.MOV
   ```

   (Don't have the folder yet? Just run step 2 with a new id — it creates the
   folder and tells you to drop the videos in.)

2. **Process** it with one command (run from `code/`):

   ```bash
   .venv\Scripts\python.exe scripts\build_foot_trajectory.py test01
   ```

   A bare number also works: `... build_foot_trajectory.py 1` → `test01`.

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
- Calibration (`calibration/*.npz`) is shared across all tests — do **not**
  move the cameras between tests, or you must re-run the extrinsics + world
  transform.
- Naming is up to you: `test01`, `P03_obstacle2`, `pilot_clap` all work — the id
  becomes the folder name and the prefix on every output file.
