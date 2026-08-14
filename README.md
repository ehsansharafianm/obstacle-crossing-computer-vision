# Obstacle Crossing — Camera + IMU Trajectory Study

3D marker-trajectory measurement of foot behavior during obstacle crossing.
Consumer cameras (iPad) are the **primary** spatial measurement source; Movella
DOT / Awinda IMUs supply gait-event timing. Research question: does static
postural-control performance predict toe-clearance, foot-placement, and
arm-swing behavior during obstacle crossing?

## Two halves of this repository

| Folder     | What lives here                                         | Read it in |
|------------|---------------------------------------------------------|------------|
| **`code/`** | All Python code, data, calibration, results — the pipeline | An IDE / terminal |
| **`docs/`** | All markdown notes: design rationale, protocols, decisions | **Obsidian** (open `docs/` as a vault) |

- Engineering work → **[code/](code/)** (see [code/README.md](code/README.md))
- Study design, rationale, lab protocols → **[docs/](docs/)** (open as an Obsidian vault)

Keeping notes separate from code means the `docs/` folder is a clean Obsidian
vault — no source files cluttering the graph — while `code/` stays a tidy
software project.
