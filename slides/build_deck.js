const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.layout = "LAYOUT_WIDE";           // 13.3 x 7.5
const W = 13.3, H = 7.5;

// palette
const NAVY = "0F2A43", NAVY2 = "16395C", TEAL = "1C7293", MINT = "2EC4B6",
      RED = "E63946", WHITE = "FFFFFF", INK = "1B2A3A", MUTED = "5C6B7A",
      LIGHT = "F4F7FA", CARD = "FFFFFF";
const HEAD = "Cambria", BODY = "Calibri";

const sh = () => ({ type: "outer", color: "20344A", blur: 8, offset: 3, angle: 90, opacity: 0.28 });

function badge(s, x, y, n, color) {
  s.addShape(p.ShapeType.ellipse, { x, y, w: 0.42, h: 0.42, fill: { color }, shadow: sh() });
  s.addText(String(n), { x, y, w: 0.42, h: 0.42, align: "center", valign: "middle",
    fontFace: BODY, fontSize: 16, bold: true, color: WHITE, margin: 0 });
}

// ---------- Slide 1 : Title (dark) ----------
let s = p.addSlide();
s.background = { color: NAVY };
s.addShape(p.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: NAVY } });
s.addImage({ path: "img/setup_detection.jpg", x: 7.55, y: 0, w: 5.75, h: H, sizing: { type: "cover", w: 5.75, h: H } });
s.addShape(p.ShapeType.rect, { x: 7.55, y: 0, w: 0.08, h: H, fill: { color: MINT } });
s.addText("PROGRESS REPORT", { x: 0.7, y: 1.35, w: 6.6, h: 0.4, fontFace: BODY, fontSize: 14,
  bold: true, color: MINT, charSpacing: 3, margin: 0 });
s.addText("3D Foot-Trajectory Measurement\nfor Obstacle Crossing", { x: 0.7, y: 1.85, w: 6.7, h: 1.9,
  fontFace: HEAD, fontSize: 34, bold: true, color: WHITE, lineSpacingMultiple: 1.05, margin: 0 });
s.addText("Turning two consumer iPads into a validated ~2 mm 3D motion-capture system", {
  x: 0.7, y: 3.75, w: 6.6, h: 0.9, fontFace: BODY, fontSize: 16, color: "CFE3EF", margin: 0 });
s.addText([{ text: "Ehsan Sharafian", options: { bold: true, color: WHITE } },
           { text: "   ·   Biomechanics Lab   ·   August 2026", options: { color: "9DB4C6" } }],
  { x: 0.7, y: 6.3, w: 6.6, h: 0.4, fontFace: BODY, fontSize: 13, margin: 0 });

// ---------- Slide 2 : Goal & Approach (light) ----------
s = p.addSlide();
s.background = { color: LIGHT };
s.addText("Goal & Approach", { x: 0.7, y: 0.55, w: 9, h: 0.7, fontFace: HEAD, fontSize: 32, bold: true, color: NAVY, margin: 0 });
s.addText("Measure foot clearance and placement during obstacle crossing in 3D — using cameras as the PRIMARY spatial measurement source, with IMUs for gait-event timing.",
  { x: 0.7, y: 1.35, w: 7.0, h: 1.0, fontFace: BODY, fontSize: 15.5, color: INK, margin: 0, lineSpacingMultiple: 1.1 });

const rows = [
  ["Two iPads (10th gen)", "1080p @ 240 fps, locked focus/exposure, 1x lens"],
  ["Camera calibration", "ChArUco board → lens intrinsics + stereo geometry"],
  ["Coloured foot markers", "distinct colours (red / teal / magenta) tracked in 3D"],
  ["IMU (Movella DOT / Awinda)", "gait events + camera–IMU sync to find each crossing"],
];
let y = 2.7;
rows.forEach((r, i) => {
  s.addShape(p.ShapeType.roundRect, { x: 0.7, y, w: 7.0, h: 0.86, rectRadius: 0.08, fill: { color: CARD }, line: { color: "DCE6EE", width: 1 }, shadow: sh() });
  badge(s, 0.95, y + 0.22, i + 1, i % 2 ? TEAL : MINT);
  s.addText(r[0], { x: 1.55, y: y + 0.10, w: 6.0, h: 0.36, fontFace: BODY, fontSize: 15, bold: true, color: NAVY, margin: 0, valign: "middle" });
  s.addText(r[1], { x: 1.55, y: y + 0.44, w: 6.0, h: 0.34, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0, valign: "middle" });
  y += 0.98;
});
s.addImage({ path: "img/setup_view2.jpg", x: 8.1, y: 1.35, w: 4.5, h: 5.3, sizing: { type: "cover", w: 4.5, h: 5.3 }, shadow: sh() });
s.addText("Lab capture volume (floor-taped crossing zone), two-camera view", { x: 8.1, y: 6.7, w: 4.5, h: 0.35, fontFace: BODY, fontSize: 10.5, italic: true, color: MUTED, align: "center", margin: 0 });

// ---------- Slide 3 : Calibration & Accuracy (light) ----------
s = p.addSlide();
s.background = { color: LIGHT };
s.addText("Calibration & Accuracy Validation", { x: 0.7, y: 0.55, w: 12, h: 0.7, fontFace: HEAD, fontSize: 32, bold: true, color: NAVY, margin: 0 });

// hero stat card
s.addShape(p.ShapeType.roundRect, { x: 0.7, y: 1.5, w: 5.2, h: 2.5, rectRadius: 0.1, fill: { color: NAVY }, shadow: sh() });
s.addText("≈ 2 mm", { x: 0.7, y: 1.75, w: 5.2, h: 1.2, fontFace: HEAD, fontSize: 60, bold: true, color: MINT, align: "center", margin: 0 });
s.addText("3D reconstruction accuracy", { x: 0.7, y: 2.95, w: 5.2, h: 0.4, fontFace: BODY, fontSize: 16, bold: true, color: WHITE, align: "center", margin: 0 });
s.addText("validated against a rigid wand with known marker distances", { x: 0.9, y: 3.35, w: 4.8, h: 0.5, fontFace: BODY, fontSize: 12, color: "AFc6d6".toUpperCase(), align: "center", margin: 0 });

const facts = [
  ["Lens intrinsics", "both cameras stable & sub-pixel"],
  ["Stereo geometry", "0.74 px error · 2.04 m baseline"],
  ["Wand accuracy test", "2.1 mm (clean poses) across the volume"],
];
y = 4.25;
facts.forEach((f) => {
  s.addShape(p.ShapeType.roundRect, { x: 0.7, y, w: 5.2, h: 0.82, rectRadius: 0.07, fill: { color: CARD }, line: { color: "DCE6EE", width: 1 } });
  s.addShape(p.ShapeType.ellipse, { x: 0.92, y: y + 0.27, w: 0.28, h: 0.28, fill: { color: TEAL } });
  s.addText(f[0], { x: 1.4, y: y + 0.09, w: 4.3, h: 0.34, fontFace: BODY, fontSize: 13.5, bold: true, color: NAVY, margin: 0, valign: "middle" });
  s.addText(f[1], { x: 1.4, y: y + 0.42, w: 4.3, h: 0.32, fontFace: BODY, fontSize: 12, color: MUTED, margin: 0, valign: "middle" });
  y += 0.92;
});

s.addImage({ path: "img/board.png", x: 6.4, y: 1.5, w: 6.2, h: 4.0, sizing: { type: "contain", w: 6.2, h: 4.0 }, shadow: sh() });
s.addText("ChArUco calibration board (printed & measured)", { x: 6.4, y: 5.55, w: 6.2, h: 0.35, fontFace: BODY, fontSize: 11, italic: true, color: MUTED, align: "center", margin: 0 });
s.addText("Method: calibrate once → reuse for every session. Accuracy proven end-to-end before collecting any participant data.",
  { x: 6.4, y: 6.05, w: 6.2, h: 0.8, fontFace: BODY, fontSize: 13, color: INK, margin: 0, lineSpacingMultiple: 1.1 });

// ---------- Slide 4 : Trajectory result (light) ----------
s = p.addSlide();
s.background = { color: LIGHT };
s.addText("Result: 3D Marker Trajectory in Motion", { x: 0.7, y: 0.55, w: 12, h: 0.7, fontFace: HEAD, fontSize: 32, bold: true, color: NAVY, margin: 0 });
s.addImage({ path: "img/trajectory.png", x: 4.7, y: 1.4, w: 8.1, h: 5.6, sizing: { type: "contain", w: 8.1, h: 5.6 }, shadow: sh() });

const pts = [
  ["First moving 3D trajectory", "markers tracked & triangulated at every frame as the wand moves"],
  ["Validation", "the rigid wand's known distances stay flat through the motion — sync + tracking + triangulation all work together"],
  ["Output", "per-frame X / Y / Z for each marker, exported to CSV"],
];
y = 1.55;
pts.forEach((pt, i) => {
  badge(s, 0.7, y, i + 1, i % 2 ? TEAL : MINT);
  s.addText(pt[0], { x: 1.3, y: y - 0.05, w: 3.2, h: 0.4, fontFace: BODY, fontSize: 15, bold: true, color: NAVY, margin: 0 });
  s.addText(pt[1], { x: 1.3, y: y + 0.36, w: 3.25, h: 1.2, fontFace: BODY, fontSize: 12.5, color: MUTED, margin: 0, lineSpacingMultiple: 1.08 });
  y += 1.55;
});
s.addText("Top: reconstructed distances stay on the known values (dotted).  Bottom: the markers' 3D paths.",
  { x: 4.7, y: 7.0, w: 8.1, h: 0.35, fontFace: BODY, fontSize: 10.5, italic: true, color: MUTED, align: "center", margin: 0 });

// ---------- Slide 5 : Status & Next (dark) ----------
s = p.addSlide();
s.background = { color: NAVY };
s.addText("Status & Next Steps", { x: 0.7, y: 0.55, w: 12, h: 0.7, fontFace: HEAD, fontSize: 32, bold: true, color: WHITE, margin: 0 });

s.addText("DONE", { x: 0.7, y: 1.5, w: 5.7, h: 0.4, fontFace: BODY, fontSize: 15, bold: true, color: MINT, charSpacing: 3, margin: 0 });
const done = ["Two-iPad system calibrated (intrinsics + stereo)", "3D accuracy validated — ~2 mm", "Coloured-marker detection & tracking", "Camera-to-camera synchronisation", "Moving 3D trajectory + CSV export", "Trajectory cleaning (filter / gap-fill)"];
s.addText(done.map((t, i) => ({ text: t, options: { bullet: { code: "2713" }, color: "E6EEF4", breakLine: true, paraSpaceAfter: 8 } })),
  { x: 0.7, y: 2.0, w: 5.9, h: 4.6, fontFace: BODY, fontSize: 14.5, color: "E6EEF4", margin: 0 });

s.addShape(p.ShapeType.roundRect, { x: 6.9, y: 1.5, w: 5.7, h: 5.1, rectRadius: 0.1, fill: { color: NAVY2 }, shadow: sh() });
s.addText("NEXT", { x: 7.2, y: 1.75, w: 5.1, h: 0.4, fontFace: BODY, fontSize: 15, bold: true, color: MINT, charSpacing: 3, margin: 0 });
const next = ["Foot pilot: markers on a shoe, one obstacle crossing", "IMU sync + gait events → locate each crossing", "Compute clearance & foot-placement metrics", "Automated one-command pipeline per participant", "Scale: 6 obstacles × 5 crossings, many participants"];
s.addText(next.map((t) => ({ text: t, options: { bullet: { code: "2192" }, color: "DCE8F0", breakLine: true, paraSpaceAfter: 10 } })),
  { x: 7.2, y: 2.3, w: 5.15, h: 3.6, fontFace: BODY, fontSize: 14.5, margin: 0 });
s.addText("The hardest technical risk — mm-accuracy from consumer cameras — is already retired.",
  { x: 7.2, y: 5.9, w: 5.15, h: 0.7, fontFace: BODY, fontSize: 12.5, italic: true, bold: true, color: MINT, margin: 0, lineSpacingMultiple: 1.05 });

p.writeFile({ fileName: "obstacle_crossing_update.pptx" }).then(f => console.log("wrote", f));
