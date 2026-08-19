const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";           // 13.3 x 7.5
const W = 13.3, H = 7.5;

// palette
const NAVY = "0F2A43", NAVY2 = "16395C", TEAL = "1C7293", MINT = "2EC4B6",
      PURPLE = "7C3AED", GREEN = "22A559", RED = "E63946", WHITE = "FFFFFF",
      INK = "1B2A3A", MUTED = "5C6B7A", LIGHT = "F4F7FA", CARD = "FFFFFF";
const HEAD = "Cambria", BODY = "Calibri";

const sh = () => ({ type: "outer", color: "20344A", blur: 8, offset: 3, angle: 90, opacity: 0.28 });

function badge(s, x, y, n, color) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: 0.42, h: 0.42, fill: { color }, shadow: sh() });
  s.addText(String(n), { x, y, w: 0.42, h: 0.42, align: "center", valign: "middle",
    fontFace: BODY, fontSize: 16, bold: true, color: WHITE, margin: 0 });
}
function title(s, txt, color) {
  s.addText(txt, { x: 0.7, y: 0.5, w: 12, h: 0.75, fontFace: HEAD, fontSize: 31, bold: true, color: color || NAVY, margin: 0 });
  s.addShape(p.ShapeType.rect, { x: 0.72, y: 1.28, w: 1.5, h: 0.06, fill: { color: MINT } });
}
function cap(s, txt, x, y, w) {
  s.addText(txt, { x, y, w, h: 0.35, fontFace: BODY, fontSize: 10.5, italic: true, color: MUTED, align: "center", margin: 0 });
}

// ================= Slide 1 : Title =================
let s = p.addSlide();
s.background = { color: NAVY };
s.addImage({ path: "img/crossing_hero.jpg", x: 7.15, y: 0, w: 6.15, h: H, sizing: { type: "cover", w: 6.15, h: H } });
s.addShape(p.ShapeType.rect, { x: 7.15, y: 0, w: 0.09, h: H, fill: { color: MINT } });
s.addShape(p.ShapeType.rect, { x: 7.15, y: 0, w: 6.15, h: H, fill: { color: NAVY, transparency: 55 } });
s.addText("PROGRESS UPDATE  ·  AUGUST 2026", { x: 0.7, y: 1.25, w: 6.4, h: 0.4, fontFace: BODY, fontSize: 13.5,
  bold: true, color: MINT, charSpacing: 3, margin: 0 });
s.addText("3D Foot-Clearance Tracking\nfor Obstacle Crossing", { x: 0.7, y: 1.75, w: 6.5, h: 1.9,
  fontFace: HEAD, fontSize: 33, bold: true, color: WHITE, lineSpacingMultiple: 1.05, margin: 0 });
s.addText("A clean 3D foot trajectory from two consumer iPads — markers, calibration, sync and clearance validated end-to-end.",
  { x: 0.7, y: 3.75, w: 6.3, h: 1.0, fontFace: BODY, fontSize: 16, color: "CFE3EF", margin: 0, lineSpacingMultiple: 1.12 });
s.addText([{ text: "Ehsan Sharafian", options: { bold: true, color: WHITE } },
           { text: "   ·   Biomechanics Lab", options: { color: "9DB4C6" } }],
  { x: 0.7, y: 6.35, w: 6.4, h: 0.4, fontFace: BODY, fontSize: 13, margin: 0 });

// ================= Slide 2 : Markers & Detection =================
s = p.addSlide();
s.background = { color: LIGHT };
title(s, "Foot Markers & Detection");
const mk = [
  ["Two spherical markers on the shoe", "purple = toe, green = heel"],
  ["Unique colours", "tracked automatically in both cameras — no manual digitising"],
  ["Spherical shape", "looks the same from every angle as the foot rotates"],
  ["Triangulated to 3D", "each marker reconstructed when seen by both cameras"],
];
let y = 1.75;
mk.forEach((r, i) => {
  s.addShape(p.ShapeType.roundRect, { x: 0.7, y, w: 5.55, h: 0.92, rectRadius: 0.08, fill: { color: CARD }, line: { color: "DCE6EE", width: 1 }, shadow: sh() });
  s.addShape(p.ShapeType.ellipse, { x: 0.95, y: y + 0.31, w: 0.3, h: 0.3, fill: { color: i === 0 ? PURPLE : i === 1 ? GREEN : TEAL } });
  s.addText(r[0], { x: 1.45, y: y + 0.12, w: 4.65, h: 0.38, fontFace: BODY, fontSize: 14.5, bold: true, color: NAVY, margin: 0, valign: "middle" });
  s.addText(r[1], { x: 1.45, y: y + 0.5, w: 4.65, h: 0.34, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0, valign: "middle" });
  y += 1.05;
});
s.addImage({ path: "img/markers_closeup.jpg", x: 6.55, y: 1.75, w: 6.05, h: 3.05, sizing: { type: "cover", w: 6.05, h: 3.05 }, shadow: sh() });
cap(s, "Purple toe + green heel balls on the shoe", 6.55, 4.82, 6.05);
s.addImage({ path: "img/detection_overlay.jpg", x: 6.55, y: 5.3, w: 6.05, h: 1.85, sizing: { type: "cover", w: 6.05, h: 1.85 }, shadow: sh() });
cap(s, "Automatically detected mid-crossing (toe / heel)", 6.55, 7.12, 6.05);

// ================= Slide 3 : Calibration =================
s = p.addSlide();
s.background = { color: LIGHT };
title(s, "Camera Calibration — once per session");
s.addText("A ChArUco board gives each lens's intrinsics, the stereo geometry between the two cameras, and a floor world-frame (Z = height). One command per session; recalibrate whenever the cameras move.",
  { x: 0.7, y: 1.5, w: 5.7, h: 1.3, fontFace: BODY, fontSize: 14.5, color: INK, margin: 0, lineSpacingMultiple: 1.14 });
const facts = [
  ["Stereo reprojection error", "0.92 px  ·  baseline 1.86 m"],
  ["Floor world-frame residual", "0.65 mm  (flat, well below 3 mm)"],
  ["Recovered camera height", "986 mm  — matches the physical setup"],
];
y = 3.0;
facts.forEach((f) => {
  s.addShape(p.ShapeType.roundRect, { x: 0.7, y, w: 5.7, h: 0.98, rectRadius: 0.08, fill: { color: CARD }, line: { color: "DCE6EE", width: 1 }, shadow: sh() });
  s.addShape(p.ShapeType.ellipse, { x: 0.95, y: y + 0.35, w: 0.28, h: 0.28, fill: { color: MINT } });
  s.addText(f[0], { x: 1.4, y: y + 0.13, w: 4.8, h: 0.36, fontFace: BODY, fontSize: 14, bold: true, color: NAVY, margin: 0, valign: "middle" });
  s.addText(f[1], { x: 1.4, y: y + 0.5, w: 4.8, h: 0.34, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0, valign: "middle" });
  y += 1.1;
});
s.addImage({ path: "img/calib_board.jpg", x: 6.6, y: 1.5, w: 6.0, h: 2.65, sizing: { type: "cover", w: 6.0, h: 2.65 }, shadow: sh() });
cap(s, "Extrinsics: board held static at many poses (both cameras)", 6.6, 4.17, 6.0);
s.addImage({ path: "img/calib_floor.jpg", x: 6.6, y: 4.6, w: 6.0, h: 2.5, sizing: { type: "cover", w: 6.0, h: 2.5 }, shadow: sh() });
cap(s, "World frame: board flat on the floor (Z = up)", 6.6, 7.12, 6.0);

// ================= Slide 4 : Synchronisation =================
s = p.addSlide();
s.background = { color: LIGHT };
title(s, "Synchronising the Cameras — one clap");
s.addImage({ path: "img/clap.png", x: 4.55, y: 1.7, w: 8.15, h: 3.25, sizing: { type: "contain", w: 8.15, h: 3.25 } });
const syncpts = [
  ["One sharp clap at the start", "a single loud spike in both cameras' audio"],
  ["Aligned to the millisecond", "cross-correlate the two audio tracks — no hardware sync"],
  ["Works off-camera", "audio only — you needn't be in the frame"],
  ["test06 lock", "cam2 + (−5.46 s), confidence 55"],
];
y = 1.75;
syncpts.forEach((pt, i) => {
  badge(s, 0.7, y, i + 1, i % 2 ? TEAL : MINT);
  s.addText(pt[0], { x: 1.3, y: y - 0.04, w: 2.9, h: 0.4, fontFace: BODY, fontSize: 14, bold: true, color: NAVY, margin: 0 });
  s.addText(pt[1], { x: 1.3, y: y + 0.38, w: 3.0, h: 0.9, fontFace: BODY, fontSize: 12, color: MUTED, margin: 0, lineSpacingMultiple: 1.08 });
  y += 1.28;
});
s.addShape(p.ShapeType.roundRect, { x: 4.55, y: 5.35, w: 8.15, h: 1.55, rectRadius: 0.1, fill: { color: NAVY }, shadow: sh() });
s.addText("After sync: outliers are gated (physically-impossible points dropped) and a rigid-shoe check removes mis-triangulated frames — leaving honest gaps where the foot is out of view.",
  { x: 4.85, y: 5.5, w: 7.55, h: 1.25, fontFace: BODY, fontSize: 13.5, color: "E6EEF4", margin: 0, valign: "middle", lineSpacingMultiple: 1.14 });

// ================= Slide 5 : Result — Trajectory =================
s = p.addSlide();
s.background = { color: LIGHT };
title(s, "Result: 3D Foot-Clearance Trajectory");
s.addImage({ path: "img/trajectory.png", x: 4.55, y: 1.45, w: 8.2, h: 5.6, sizing: { type: "contain", w: 8.2, h: 5.6 }, shadow: sh() });
const res = [
  ["Clear clearance arcs", "toe & heel rise ~300–500 mm over each crossing, return to a flat ~60 mm baseline"],
  ["Rigid-body check passes", "toe–heel distance holds ~294 mm (= shoe length), std 17 mm"],
  ["Metric 3D output", "per-frame X / Y / Z + time for each marker → CSV, one file per test"],
];
y = 1.65;
res.forEach((r, i) => {
  badge(s, 0.7, y, i + 1, i % 2 ? TEAL : MINT);
  s.addText(r[0], { x: 1.3, y: y - 0.05, w: 3.0, h: 0.4, fontFace: BODY, fontSize: 14.5, bold: true, color: NAVY, margin: 0 });
  s.addText(r[1], { x: 1.3, y: y + 0.4, w: 3.05, h: 1.4, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0, lineSpacingMultiple: 1.1 });
  y += 1.75;
});
cap(s, "Top: toe/heel height over time (clearance).  Bottom: toe–heel distance stays flat = clean 3D.", 4.55, 7.08, 8.2);

// ================= Slide 6 : Status & Next =================
s = p.addSlide();
s.background = { color: NAVY };
s.addText("Status & Next Steps", { x: 0.7, y: 0.5, w: 12, h: 0.75, fontFace: HEAD, fontSize: 31, bold: true, color: WHITE, margin: 0 });
s.addShape(p.ShapeType.rect, { x: 0.72, y: 1.28, w: 1.5, h: 0.06, fill: { color: MINT } });
s.addText("WORKING", { x: 0.7, y: 1.6, w: 5.7, h: 0.4, fontFace: BODY, fontSize: 14, bold: true, color: MINT, charSpacing: 3, margin: 0 });
const done = ["Per-session calibration (validated: 0.9 px, 0.65 mm floor)",
  "Spherical purple-toe / green-heel marker tracking",
  "One-clap audio synchronisation (no hardware)",
  "Clean 3D trajectory with real clearance arcs",
  "Rigid-shoe check: toe–heel std ~17 mm",
  "One-command workflow (run_calib / run_test) + CSV"];
s.addText(done.map((t) => ({ text: t, options: { bullet: { code: "2713" }, color: "E6EEF4", breakLine: true, paraSpaceAfter: 9 } })),
  { x: 0.7, y: 2.1, w: 5.95, h: 4.6, fontFace: BODY, fontSize: 14.5, margin: 0 });
s.addShape(p.ShapeType.roundRect, { x: 6.9, y: 1.6, w: 5.7, h: 5.05, rectRadius: 0.1, fill: { color: NAVY2 }, shadow: sh() });
s.addText("NEXT", { x: 7.2, y: 1.85, w: 5.1, h: 0.4, fontFace: BODY, fontSize: 14, bold: true, color: MINT, charSpacing: 3, margin: 0 });
const next = ["Raise coverage — continuous crossings so the foot stays in both views",
  "Add a 3rd camera (Pixel 8) to remove occlusion",
  "Collect a participant pilot across obstacles",
  "Fold in gait-event timing for each crossing"];
s.addText(next.map((t) => ({ text: t, options: { bullet: { code: "2192" }, color: "DCE8F0", breakLine: true, paraSpaceAfter: 12 } })),
  { x: 7.2, y: 2.35, w: 5.15, h: 3.2, fontFace: BODY, fontSize: 14.5, margin: 0 });
s.addText("The full measurement chain works — from raw video to a clean 3D clearance curve.",
  { x: 7.2, y: 5.75, w: 5.15, h: 0.8, fontFace: BODY, fontSize: 13, italic: true, bold: true, color: MINT, margin: 0, lineSpacingMultiple: 1.08 });

p.writeFile({ fileName: "obstacle_crossing_update.pptx" }).then(f => console.log("wrote", f));
