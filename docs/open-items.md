# Open items to resolve before finalizing

Decisions to lock down before full data collection. From [[camera-imu-workflow]] §9.

- [ ] Confirm total crossing count structure (per-obstacle vs. total across all
      obstacles) — sizes the digitizing-labor estimate; changes workload a lot
- [ ] Confirm DOT–Awinda mutual sync status (may already be solved via prior BLE work)
- [ ] Decide exact obstacle marker placement (which reference points per geometry)
- [ ] Decide final iPad camera count — 2 vs. 3 (3 preferred for trail-limb
      occlusion **at the clearance instant**)
      - Synthetic geometry check (`code/tests/test_geometry_synthetic.py`): at
        0.3 px tracking noise and ~40°-per-side convergence, reconstruction RMS
        was **2.0 mm with 2 cameras vs. 1.1 mm with 3** — a 3rd camera roughly
        halved error *even before* accounting for occlusion. Illustrative only;
        the rod test on real cameras is the real number. Leans toward 3.
      - Same model, per-axis: **vertical (Z) rods reconstructed ~3-4x worse**
        than horizontal (RMS 2.9 mm vs 0.6-0.8 mm at 0.3 px noise). Z is your
        clearance axis, so it's the weakest link — reinforces (a) placing the
        accuracy-check rod **vertically** ([[calibration-accuracy-check]]) and
        (b) adding the 3rd camera to shore up Z. This anisotropy is exactly the
        concern behind design doc §98.
- [ ] Define fixed origin/axis convention for the capture volume
      (e.g. origin at obstacle base, X = travel, Y = mediolateral, Z = vertical)
- [ ] Plan calibration accuracy-check protocol → [[calibration-accuracy-check]]
- [ ] Choose/build marker-detection approach in OpenCV (color vs. reflective+IR,
      blob-detector params) and validate against manual digitizing on a frame subset

## Resolved

_(move items here with the decision + date as they're settled)_
