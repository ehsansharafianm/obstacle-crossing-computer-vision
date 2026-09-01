# Pre-Recording Checklist — get test14-quality results every time

Run through this before **every** capture session. It's what turned test14 into clean
data (obstacle 75 % coverage, sub-mm scatter, feet 15/13 mm). The pipeline fixes are
already in the code — this checklist covers the part **you** control at recording time.
See [[2026-08-29]] for the story and [[next-steps]] for the roadmap.

## Before you start (setup)
- [ ] **Cameras have NOT moved since calibration.** This is the #1 rule. If any tripod was
      bumped or moved, the extrinsics + floor calibration are silently wrong — redo them
      (`build_calibration N`, see [[calibration-session-recording]]). No error will warn you.
- [ ] **All 3 phones: stabilization OFF**, ultrawide 60 fps, same locked settings as
      calibration ([[pixel-slowmo-calibration-setup]]).
- [ ] **Markers are clean, spherical, saturated:** purple toe + green heel (feet),
      red-orange balls (obstacle). Faded/dirty/dusty markers drop detection.
- [ ] **Obstacle sits in the shared view of at least 2 cameras** (ideally cam1 + cam2, the
      precision core). A marker needs ≥2 cameras to become a 3D point.

## During the recording
- [ ] **One loud, clear clap at the very start** of every clip (can be off-frame). All three
      cameras sync to it — a weak clap is the biggest sync risk.
- [ ] **Let the obstacle sit completely still** while recording each height. The sub-mm
      obstacle numbers come from a static target over many frames — don't nudge it mid-config.
- [ ] When changing height between configs, **pause, reposition, then hold still again.**
      The gap is fine; the pipeline finds each static window.
- [ ] Walk the crossings **along Y** (obstacle bar along X), per the calibrated layout.

## After processing — sanity-check the run log (`results/sessions/<id>/<id>_run.txt`)
A good session shows all of these. If any is off, the session is suspect — reshoot rather
than trust it.
- [ ] **`[clap agrees]` on cam2 AND cam3** (not `[clap OFF]`).
- [ ] **Feet toe-heel std ~10–20 mm** ("dropped N outliers" should be modest).
- [ ] **Obstacle coverage 50 %+** ("Obstacle markers reconstructed in X/Y frames").
- [ ] Obstacle Z per config is **flat with a tight IQR** (check the trajectory plot / xlsx).
- [ ] Foot Z shows clean **lift/landing arcs** at every crossing.

## The one remaining fragility
The obstacle balls are **orange-red — the same hue as skin and the orange support poles.**
The hue + round-blob shape gate handles it now (see [[obstacle-red-marker-detection]]), but
it's the only detection with no hue margin. For the **6-height protocol**, a **blue** obstacle
ball would remove this risk entirely — nothing else in the room is blue, and the feet already
use purple/green/teal/pink. Optional, but the safest choice for a protocol run many times.

## Quick reference — what each safeguard protects
| Safeguard | Protects against |
|---|---|
| Don't move cameras | Silently wrong 3D (worst failure — no warning) |
| Loud clap | Camera sync drifting / aliasing |
| Clean saturated markers | Missed detections, low coverage |
| Obstacle static per config | Noisy obstacle height |
| Obstacle in ≥2 camera views | Marker never becomes 3D |
| Check the run log | Trusting a bad session |
