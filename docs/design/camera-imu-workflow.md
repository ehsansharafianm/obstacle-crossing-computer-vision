# Obstacle Crossing: Camera + IMU Trajectory Study — Design Summary & Workflow

## 1. Research context

**Background project:** Ehsan's ongoing obstacle-crossing research uses Movella
DOT and Awinda IMUs, an OpenSim/OpenSense pipeline (IMUPlacer →
IMUInverseKinematicsTool → WBAM computation), and an Android capture app
(`ObjectCrossing`) with Firebase storage.

**Motivating paper:** Magalhães et al., "The influence of postural control on
toe clearance during stair negotiation in older adults," *Gait & Posture*
123 (2026) 110004. That study found static postural control performance
(center-of-pressure sway amplitude/velocity in semi-tandem and single-leg
stances) partly predicts toe clearance behavior during stair ascent/descent,
using 2-camera 2D videogrammetry (single marker per foot, Dvideow software,
DLT-style reconstruction) with toe clearance sampled at only two discrete
moments (landing, transition) rather than as a continuous trajectory. Their
own stated limitation: this doesn't capture *minimum* toe clearance (lowest
point of the sole).

**New research question:** Does static postural control performance predict
toe clearance and foot-placement behavior during **obstacle crossing**
(not stairs)? Potential extension beyond the original paper: does it also
predict **arm-swing compensation**, a gap already identified in the
obstacle-crossing project.

## 2. What the camera system is for

The camera-derived 3D marker trajectories are a **primary measurement
source for spatial parameters**, not a validation check against the IMU
system (the IMU system has already been validated separately). Camera data
supplies distance/clearance information the IMUs don't directly give.

**Three target variables per crossing, per limb:**
1. **Pre-obstacle distance** — horizontal distance from lead-limb toe
   marker to the obstacle's near edge, at last foot-contact before crossing
2. **Vertical clearance** — minimum vertical gap between foot marker(s) and
   obstacle top edge during the swing phase over the obstacle
3. **Post-obstacle distance** — horizontal distance from trail-limb heel
   marker to the obstacle's far edge, at first foot-contact after crossing

## 3. Study design

- **6 different obstacles**, varying dimensions/geometry
- Crossings organized in **laps** (confirm total crossing count per
  obstacle vs. total across all obstacles before finalizing digitizing
  labor estimate — this changes workload significantly)
- **Markers:**
  - Shoe: 6 markers per foot, both feet (12 markers per participant) —
    gives full segment orientation, not just toe/heel points, which helps
    resolve the true minimum clearance point rather than relying on a
    single marker's height
  - Obstacle: a few markers per obstacle at key reference points (exact
    edges/corners to be decided per obstacle geometry) — static once
    placed, so no need to track every frame; digitize once per obstacle
    placement
- **Event timing (toe-off / heel-strike):** derived from the existing,
  independently-validated DOT/Awinda IMU pipeline — no foot switches or
  force plates needed
- **Recording strategy:** one continuous recording per session spanning
  all laps/obstacles, not separate clips per trial

## 4. Camera hardware and geometry

- **Chosen hardware: iPad (10th gen)** — less lens distortion than a
  GoPro's wide-angle lens (easier calibration), higher slow-mo frame rate
  available (up to 240fps @ 1080p). **Must lock AE/AF manually before every
  recording** (tap-and-hold, or a manual-focus camera app) — continuous
  autofocus otherwise shifts effective focal length mid-session and breaks
  the fixed-intrinsics assumption calibration depends on
- **Camera count:** 2 minimum (sagittal + oblique, ~60–90° convergence
  angle at the capture volume for good triangulation geometry); 3 preferred
  to reduce occlusion of trail-limb markers around the obstacle (add a
  second oblique camera on the opposite side)
- **Calibration:** wand or checkerboard-based, spanning the full capture
  volume; must be redone if cameras are physically moved between sessions

## 5. Sync strategy (cameras + DOT + Awinda)

- **No hardware sync between GoPros/iPads and IMUs** — use a shared,
  sharp physical anchor event (clap, tap, or LED flash) visible/detectable
  in all three data streams simultaneously
- Do this **once at the start** and **once at the end** of the continuous
  recording, to check for clock drift across the session; if start- and
  end-anchor alignments agree, a single sync point was sufficient — if not,
  interpolate the timing correction across the session
- **Open item:** confirm whether DOT and Awinda are already synced to each
  other (may already be solved given prior BLE work) — this is a third
  potential sync gap distinct from camera-to-IMU sync

## 6. Processing pipeline

1. **Calibration** — camera intrinsics/extrinsics from wand or checkerboard
   (DLTdv8 + easyWand, or OpenCV `cv2.calibrateCamera` /
   `cv2.stereoCalibrate`)
2. **Calibration accuracy check** — reconstruct a rigid object of known
   length placed at multiple positions/orientations (including vertically,
   since clearance is a Z-axis measurement) through the full pipeline;
   report mean/RMS error in mm — this is the "trusted measurement" evidence
   for the camera system as primary source
3. **Static obstacle digitizing** — digitize each obstacle's 4 corner
   markers once per placement (not per frame/per trial)
4. **Foot marker digitizing/tracking** — per trial, track toe + heel
   markers (both feet) through the crossing window; auto-track where
   possible, manually correct occluded frames (expect this to be the main
   labor bottleneck — budget time accordingly)
5. **3D reconstruction (triangulation)** — combine 2D tracks + calibration
   → 3D (X, Y, Z) trajectories for all markers over time
6. **Filtering** — low-pass filter (e.g. 4th-order Butterworth, ~6 Hz
   cutoff, matching precedent in the source paper)
7. **IMU sync alignment** — align camera timeline to IMU timeline using
   start/end anchor events; use IMU-detected gait events as the index into
   the continuous camera recording to locate each individual crossing
8. **Metric computation** — for each crossing, compute pre-obstacle
   distance, minimum vertical clearance, and post-obstacle distance from
   the filtered, event-aligned 3D trajectories
9. **Origin/axes** — define deliberately at calibration time (e.g. origin
   at obstacle base, X = travel direction, Y = mediolateral, Z = vertical)
   for directly interpretable output values

## 7. Software: OpenCV (chosen)

- **Calibration:** `cv2.calibrateCamera` (single camera intrinsics,
  checkerboard-based) → `cv2.stereoCalibrate` (relative pose between
  cameras)
- **Marker tracking:** custom — blob detection (`cv2.SimpleBlobDetector` or
  thresholding + centroid) for reflective/colored markers, plus frame-to-
  frame tracking (optical flow or a tracker object) for the moving foot
  markers; obstacle markers digitized once per placement, not tracked
  frame-by-frame
- **3D reconstruction:** `cv2.triangulatePoints` using the calibrated
  camera pair
- **Everything downstream** (filtering, event-window extraction, metric
  computation, IMU sync alignment) — custom Python scripts, consistent
  with the existing IMU/terrain-classification codebase

Because tracking is custom-built (not an off-the-shelf, literature-
established tracker like DLTdv8's), the validation section below is not
optional — it's the evidence backing the camera system's accuracy in the
absence of a pre-validated tool citation.

## 8. Validation requirements (given camera is a primary measurement source)

- **Mandatory:** calibration/reconstruction accuracy check (known-distance
  object, mean/RMS error reported)
- **Recommended:** repeatability check (same trial digitized twice,
  report variability)
- **If building custom tracking (OpenCV route):** marker-tracking accuracy
  check — automated detection vs. manual digitizing agreement on a subset
  of frames
- **Not needed:** full concurrent validation of camera vs. IMU — camera
  data isn't being used to validate the IMU system

## 9. Open items to resolve before finalizing

- [ ] Confirm total crossing count structure (per-obstacle vs. total) to
      size the digitizing labor estimate
- [ ] Confirm DOT–Awinda mutual sync status
- [ ] Decide exact obstacle marker placement (which reference points)
- [ ] Decide final iPad camera count (2 vs. 3) for occlusion robustness
- [ ] Define fixed origin/axis convention for the capture volume
- [ ] Plan calibration accuracy check protocol (rod, positions, repeats)
- [ ] Choose/build marker detection approach in OpenCV (color vs.
      reflective + IR, blob detector parameters) and validate against
      manual digitizing on a frame subset
