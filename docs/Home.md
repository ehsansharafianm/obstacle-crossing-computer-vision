# Obstacle Crossing — Notes Vault

Obsidian vault for the camera + IMU obstacle-crossing study. Code lives in
`../code/` (open that in an IDE, not here).

## Map of content

### Start here
- [[next-steps]] — roadmap & what to do next (living checklist)

### Design
- [[camera-imu-workflow]] — full design summary & processing workflow (source of truth for decisions)

### Protocols (run these in the lab)
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
