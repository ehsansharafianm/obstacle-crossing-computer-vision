# Obstacle Crossing — Notes Vault

Obsidian vault for the camera + IMU obstacle-crossing study. Code lives in
`../code/` (open that in an IDE, not here).

## Map of content

### Start here
- [[progress-log]] — what we've built & proven, step by step
- [[code-structure]] — how the code is organised
- [[next-steps]] — roadmap & what to do next (living checklist)

### Daily logs  (`daily-log/` — one note per working day: what we did, challenges, next moves)
- [[2026-08-28]] — **3× Pixel-8 ultrawide rig (the milestone)**: 3-camera clap sync, n-view 3D, test10 L16/R12 mm
- [[2026-08-19]] — **clean 3D foot-clearance trajectory**: purple/green markers, calib06, clap
- [[2026-08-18]] — per-test structure, the max-area bug, and audio-clap sync

### Design
- [[camera-imu-workflow]] — full design summary & processing workflow (source of truth for decisions)
- [[automated-pipeline]] — architecture for the turnkey per-participant system

### Protocols (run these in the lab)
- [[session-workflow]] — **the per-session checklist: calibrate → lock → record → process**
- [[intrinsic-calibration-capture]] — how to film the board so the lens estimate is well-constrained
- [[extrinsic-calibration-capture]] — filming both cameras together to get their relative positions
- [[calibration-accuracy-check]] — known-length rod reconstruction accuracy test
- _more to come: sync-anchor procedure, tracking-validation_

### Tracking
- [[open-items]] — decisions to lock down before data collection

## How this vault is organized

| Folder        | Contents                                        |
|---------------|-------------------------------------------------|
| `design/`     | Why the study is built the way it is            |
| `protocols/`  | Step-by-step lab procedures & checklists        |
| (root)        | This home note + cross-cutting trackers         |

Link notes with `[[wikilinks]]`. A link to a note that doesn't exist yet is
fine — it marks something worth writing.
