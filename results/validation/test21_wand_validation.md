# test21 — Rigid-wand accuracy validation

Four foot markers (purple=L_toe, green=L_heel, teal=R_heel, pink=R_toe) on a rigid
T-wand, moved through the capture volume. Calibration: calib17. Processed with
build_multi_trajectory; distances computed from the reconstructed marker positions.

## Known wand geometry (cm -> mm), from the setup diagram
Vertical arm:  purple -9- center -19- green      Horizontal arm: center -11- teal -17- pink
Direct/derived marker-to-marker (mm): purple-green 280, teal-pink 170,
purple-teal 142, green-teal 220, purple-pink 294, green-pink 338
(diagonals assume perpendicular arms).

## Measured vs known (mm)
| pair (colors)   | n    | mean  | std | known | error | ratio |
|-----------------|------|-------|-----|-------|-------|-------|
| pink-teal       | 2435 | 161.1 | 2.3 | 170   | -8.9  | 0.948 |
| purple-green    | 2443 | 259.9 | 5.1 | 280   | -20.1 | 0.928 |
| green-teal      | 2410 | 208.2 | 2.1 | 220   | -11.8 | 0.946 |
| green-pink      | 2410 | 323.5 | 3.0 | 338   | -14.5 | 0.957 |
| purple-pink     | 2408 | 277.0 | 5.7 | 294   | -17.0 | 0.942 |
| purple-teal     | 2395 | 132.4 | 3.5 | 142   | -9.6  | 0.932 |

## Findings
- PRECISION: excellent -- std 2-6 mm (~1-2% of each length); very repeatable as the
  wand moved through the volume.
- ACCURACY: a systematic ~5-6% UNDERESTIMATE. The error scales with distance
  (~5-7% on every pair) = the fingerprint of a SCALE error, not noise or a fixed offset.
  Mean scale factor ~0.94 (measured is ~6% small).

## Most likely cause & fix
A pure scale error points to the calibration board's true square size. The pipeline
was told the large board squares are 62.9 mm (results/calibration/active/board_measured_large.json).
If the real squares are ~66-67 mm, that alone gives ~0.944 (62.9/66.6) -- matches.
Fix: re-measure the board squares with calipers; if larger, update board_measured_large.json
and re-run build_calibration 17. Also re-verify the wand marker center-to-center spacings.
Interim: multiply reconstructed distances by ~1.06.

Generated from results/sessions/test21/test21_trajectory.xlsx.
