# Automated Pipeline — Architecture

Goal: a **turnkey system** the lab runs per participant with no per-session
coding. Record → one command → CSV trajectories + metrics. See [[next-steps]].

## Two tiers

### Tier 1 — Setup (once per lab configuration)
- Intrinsics: once per iPad (`run_intrinsics.py`). ✅ built.
- Extrinsics: once per camera placement (`run_stereo_ransac.py`). ✅ built.
- Define the **world frame** (origin at obstacle, X=travel, Y=ML, Z=vertical).
- Outputs saved to `calibration/` — reused by every session.

### Tier 2 — Per session (the repeatable, automated part)
`occ process <session_dir>` reads a **config** + videos + calibration and runs:
1. marker tracking (`occ.tracking`) ✅
2. camera sync (wand/clap/self-consistency) ✅ (wand); clap detector = TODO
3. triangulation over time (`occ.reconstruct`) ✅
4. transform to world frame — TODO
5. filtering (Butterworth ~6 Hz) — TODO
6. IMU sync + gait-event windows — TODO
7. metric computation (pre/clearance/post) — TODO
8. write CSV: trajectories + per-crossing metrics — TODO

## Config-driven (no code edits per participant)
A per-session `session.yaml` / `.json`:
```
participant: P01
videos: {cam1: cam1.MOV, cam2: cam2.MOV}
calibration: ../../calibration/
markers: {toe: red, heel: green, mid: yellow}
obstacle: {id: A, ...}
imu: {dir: imu_exports/, sync: clap}
```

## Outputs (per session)
- `trajectories.csv` — time, marker, X/Y/Z (world frame, mm)
- `metrics.csv` — per crossing: pre-obstacle distance, min vertical clearance,
  post-obstacle distance, per limb
- QC figures (coverage, distance-constancy, trajectory plots)

## Honest limits
- Occlusion/tracking dropouts may need **manual fix** for some frames
  (the "digitizing labor" of the design doc). Plan: a **review-and-fix** step
  (flag low-confidence frames, quick manual correction), not full re-processing.
- Good round, high-contrast, distinct-coloured markers minimise this.

## Build order
1. World-frame definition + transform.
2. Filtering + gap-fill + outlier rejection (clean trajectories).
3. Session config + `occ process` CLI (single-command per session).
4. IMU sync + gait events + metric computation.
5. Batch mode + QC report.
6. Review-and-fix tool for occluded frames.
