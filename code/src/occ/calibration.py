"""Camera calibration — ChArUco-based, for OpenCV 5.0.

Strategy (see docs/design/camera-imu-workflow.md and the calibration notes):

* **Intrinsics** (focal length, principal point, lens distortion) are a
  property of each iPad with AE/AF locked. Calibrate ONCE per camera, up close,
  with the board filling the frame at many tilts/distances. -> `calibrate_intrinsics`.
* **Extrinsics** (relative pose of the camera pair) change whenever a camera
  moves, so they are solved per setup. -> `stereo_calibrate` (added next stage).

ChArUco is chosen over a plain checkerboard because each marker is individually
identified, so the board need not be fully visible — this tolerates the wide
(60-90 deg) inter-camera convergence angle of this study far better.

All lengths are in **metres**. Reconstructed 3D output is therefore in metres.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np
from cv2 import aruco


# --------------------------------------------------------------------------- #
# Board definition
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BoardSpec:
    """Physical description of the ChArUco calibration board.

    squares_x, squares_y : number of chessboard squares across / down.
    square_len_m         : side length of one chessboard square, in METRES.
    marker_len_m         : side length of the ArUco marker inside a square, in METRES.
                           Must be < square_len_m (markers sit inside white squares).
    dict_name            : name of a predefined ArUco dictionary (e.g. 'DICT_5X5_100').
    """
    squares_x: int = 8
    squares_y: int = 6
    square_len_m: float = 0.030
    marker_len_m: float = 0.023
    dict_name: str = "DICT_5X5_100"

    @staticmethod
    def from_measured_json(path: str | Path) -> "BoardSpec":
        """Load a BoardSpec from a board_measured.json (true printed sizes).

        Use this instead of the nominal defaults so reconstruction is metrically
        correct: printers rescale, and the measured square size is what matters.
        """
        import json
        d = json.loads(Path(path).read_text())
        return BoardSpec(
            squares_x=int(d["squares_x"]),
            squares_y=int(d["squares_y"]),
            square_len_m=float(d["square_len_m"]),
            marker_len_m=float(d["marker_len_m"]),
            dict_name=str(d["dict_name"]),
        )

    def dictionary(self) -> aruco.Dictionary:
        return aruco.getPredefinedDictionary(getattr(aruco, self.dict_name))

    def board(self) -> aruco.CharucoBoard:
        return aruco.CharucoBoard(
            (self.squares_x, self.squares_y),
            self.square_len_m,
            self.marker_len_m,
            self.dictionary(),
        )


# --------------------------------------------------------------------------- #
# Printable board generation
# --------------------------------------------------------------------------- #
def generate_board_image(spec: BoardSpec, dpi: int = 300,
                         margin_mm: float = 8.0,
                         ref_mm: float = 100.0) -> np.ndarray:
    """Render the board to a print-accurate image (BGR), with print-check aids.

    Printed at `dpi` and at true scale, every square measures exactly
    `spec.square_len_m`. But most print dialogs (incl. Windows Photos) rescale,
    so the sheet also carries verification aids:

      * a HORIZONTAL and a VERTICAL reference ruler of `ref_mm` (default 100 mm),
      * corner crop marks, and
      * a self-documenting label.

    After printing: measure both rulers. If they read the SAME, the print is not
    stretched. Whatever the horizontal ruler actually measures gives the true
    scale — multiply the nominal square size by (measured_ruler / ref_mm) to get
    the true printed square size to feed calibration. (Or just measure a square.)
    """
    px_per_m = dpi / 0.0254  # 1 inch = 0.0254 m

    def mm2px(mm: float) -> int:
        return round(mm / 1000.0 * px_per_m)

    board_w_px = round(spec.squares_x * spec.square_len_m * px_per_m)
    board_h_px = round(spec.squares_y * spec.square_len_m * px_per_m)
    margin_px = mm2px(margin_mm)

    board = spec.board()
    img = board.generateImage((board_w_px, board_h_px), marginSize=0)
    img = cv2.copyMakeBorder(img, margin_px, margin_px, margin_px, margin_px,
                             cv2.BORDER_CONSTANT, value=255)

    # Add bands (left + bottom) to hold the rulers, then go to colour.
    band = mm2px(30)
    img = cv2.copyMakeBorder(img, 0, band, band, 0,
                             cv2.BORDER_CONSTANT, value=255)
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    H, W = img.shape[:2]
    black = (0, 0, 0)
    ref_px = mm2px(ref_mm)
    tick = mm2px(3)

    # Horizontal reference ruler in the bottom band.
    hy = H - mm2px(15)
    hx0 = band + margin_px
    cv2.line(img, (hx0, hy), (hx0 + ref_px, hy), black, 2, cv2.LINE_AA)
    cv2.line(img, (hx0, hy - tick), (hx0, hy + tick), black, 2, cv2.LINE_AA)
    cv2.line(img, (hx0 + ref_px, hy - tick), (hx0 + ref_px, hy + tick), black, 2, cv2.LINE_AA)
    cv2.putText(img, f"{ref_mm:.0f} mm reference (measure me)",
                (hx0, hy + mm2px(9)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, black, 1, cv2.LINE_AA)

    # Vertical reference ruler in the left band.
    vx = mm2px(15)
    vy0 = margin_px
    cv2.line(img, (vx, vy0), (vx, vy0 + ref_px), black, 2, cv2.LINE_AA)
    cv2.line(img, (vx - tick, vy0), (vx + tick, vy0), black, 2, cv2.LINE_AA)
    cv2.line(img, (vx - tick, vy0 + ref_px), (vx + tick, vy0 + ref_px), black, 2, cv2.LINE_AA)
    cv2.putText(img, f"{ref_mm:.0f} mm", (vx + tick + 2, vy0 + ref_px // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, black, 1, cv2.LINE_AA)

    # Corner crop marks (if any are missing, the print was cropped).
    c = mm2px(6)
    for (cx, cy, dx, dy) in [(2, 2, 1, 1), (W - 3, 2, -1, 1),
                             (2, H - 3, 1, -1), (W - 3, H - 3, -1, -1)]:
        cv2.line(img, (cx, cy), (cx + dx * c, cy), black, 2, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + dy * c), black, 2, cv2.LINE_AA)

    # Self-documenting label along the top.
    label = (f"ChArUco {spec.squares_x}x{spec.squares_y}  nominal square="
             f"{spec.square_len_m*1000:.1f}mm  marker={spec.marker_len_m*1000:.1f}mm"
             f"  {spec.dict_name}  --  MEASURE a printed square, use that value")
    cv2.putText(img, label, (band + margin_px, mm2px(6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, black, 1, cv2.LINE_AA)
    return img


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def make_detector(spec: BoardSpec) -> aruco.CharucoDetector:
    return aruco.CharucoDetector(spec.board())


def detect_board(gray: np.ndarray, detector: aruco.CharucoDetector):
    """Detect ChArUco corners in one grayscale image.

    Returns (charuco_corners, charuco_ids) or (None, None) if not enough found.
    """
    ch_corners, ch_ids, _marker_corners, _marker_ids = detector.detectBoard(gray)
    if ch_ids is None or len(ch_ids) < 4:
        return None, None
    return ch_corners, ch_ids


# --------------------------------------------------------------------------- #
# Intrinsic calibration
# --------------------------------------------------------------------------- #
@dataclass
class Intrinsics:
    camera_matrix: np.ndarray      # 3x3
    dist_coeffs: np.ndarray        # 1xN
    image_size: tuple[int, int]    # (width, height)
    rms_reproj_error: float        # pixels
    n_views_used: int
    spec: BoardSpec

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez(path,
                 camera_matrix=self.camera_matrix,
                 dist_coeffs=self.dist_coeffs,
                 image_size=np.asarray(self.image_size),
                 rms_reproj_error=self.rms_reproj_error,
                 n_views_used=self.n_views_used,
                 spec=np.asarray([str(asdict(self.spec))], dtype=object))

    @staticmethod
    def load(path: str | Path) -> "Intrinsics":
        z = np.load(path, allow_pickle=True)
        spec = BoardSpec(**eval(str(z["spec"][0])))  # noqa: S307 (trusted local file)
        return Intrinsics(
            camera_matrix=z["camera_matrix"],
            dist_coeffs=z["dist_coeffs"],
            image_size=tuple(int(v) for v in z["image_size"]),
            rms_reproj_error=float(z["rms_reproj_error"]),
            n_views_used=int(z["n_views_used"]),
            spec=spec,
        )


def calibrate_intrinsics(image_paths: list[str | Path], spec: BoardSpec,
                         verbose: bool = True) -> Intrinsics:
    """Estimate one camera's intrinsics from many still images of the board.

    Feed 15-30 images with the board at varied distances, tilts, and positions
    (fill the frame, hit the corners — that is where distortion lives).
    """
    board = spec.board()
    detector = aruco.CharucoDetector(board)

    all_obj_pts, all_img_pts = [], []
    image_size = None
    n_seen = 0

    for p in image_paths:
        img = cv2.imread(str(p))
        if img is None:
            if verbose:
                print(f"  skip (unreadable): {p}")
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if image_size is None:
            image_size = (gray.shape[1], gray.shape[0])

        ch_corners, ch_ids = detect_board(gray, detector)
        if ch_corners is None:
            if verbose:
                print(f"  skip (board not found): {p}")
            continue

        obj_pts, img_pts = board.matchImagePoints(ch_corners, ch_ids)
        if obj_pts is None or len(obj_pts) < 4:
            continue
        all_obj_pts.append(obj_pts)
        all_img_pts.append(img_pts)
        n_seen += 1
        if verbose:
            print(f"  ok  ({len(ch_ids):3d} corners): {p}")

    if n_seen < 3:
        raise RuntimeError(
            f"Only {n_seen} usable views — need at least ~10-15 for a good fit.")

    def _per_view_errors(obj, img, mtx, dist, rvecs, tvecs):
        errs = []
        for o, i, r, t in zip(obj, img, rvecs, tvecs):
            proj, _ = cv2.projectPoints(o, r, t, mtx, dist)
            errs.append(float(np.sqrt(np.mean(
                np.sum((i.reshape(-1, 2) - proj.reshape(-1, 2)) ** 2, axis=1)))))
        return np.asarray(errs)

    # Standard (unconstrained) pinhole+distortion model. Drop only clear
    # outlier views (below) and rely on many well-varied frames for stability.
    # Fixing the principal point was tried and hurt cameras whose true centre
    # is genuinely off-image-centre, so we let it float.
    obj_pts, img_pts = all_obj_pts, all_img_pts
    for _ in range(3):
        rms, cam_mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            obj_pts, img_pts, image_size, None, None)
        errs = _per_view_errors(obj_pts, img_pts, cam_mtx, dist, rvecs, tvecs)
        cutoff = max(1.0, 2.5 * float(np.median(errs)))
        keep = errs <= cutoff
        if keep.all() or keep.sum() < 10:
            break
        dropped = (~keep).sum()
        obj_pts = [o for o, k in zip(obj_pts, keep) if k]
        img_pts = [i for i, k in zip(img_pts, keep) if k]
        if verbose:
            print(f"  dropped {dropped} outlier view(s) "
                  f"(err > {cutoff:.2f} px), recalibrating on {len(obj_pts)}")

    n_used = len(obj_pts)
    if verbose:
        print(f"\nCalibrated on {n_used} views  |  RMS reprojection error = "
              f"{rms:.4f} px")

    return Intrinsics(cam_mtx, dist, image_size, float(rms), n_used, spec)
