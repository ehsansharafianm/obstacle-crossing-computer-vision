"""Generate a LARGE ChArUco board tiled across Letter pages (for extrinsics).

Room-scale stereo calibration needs a big target: a small A4 board is only
~175 px across from ~2 m and can't be detected reliably (esp. obliquely). This
makes a ~56x42 cm board (70 mm squares, same 8x6 / DICT_5X5_100 layout) split
across 6 Letter pages you print at 100%, trim on the crop marks, butt together,
and mount on something rigid & flat.

Run from code/:
    .venv\\Scripts\\python.exe scripts\\make_big_calib_board.py

Outputs to calibration/:
  big_charuco_tiled.pdf   -> print all pages at 100% (NO fit-to-page)
  big_charuco_preview.png -> what the assembled board looks like
  board_measured_large.json (nominal; RE-MEASURE the printed ruler/squares)
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import BoardSpec, generate_board_image  # noqa: E402

DPI = 200
LETTER_W_MM, LETTER_H_MM = 215.9, 279.4
PAGE_MARGIN_MM = 10.0          # white border kept on each page


def mm2px(mm):
    return int(round(mm / 25.4 * DPI))


def main():
    spec = BoardSpec(squares_x=8, squares_y=6,
                     square_len_m=0.066, marker_len_m=0.049,
                     dict_name="DICT_5X5_100")

    # Full board incl. reference rulers, crop marks, label (reused generator).
    full = generate_board_image(spec, dpi=DPI, ref_mm=100.0)
    fh, fw = full.shape[:2]
    print(f"Full board: {spec.squares_x}x{spec.squares_y}, {spec.square_len_m*1000:.0f} mm squares "
          f"-> {fw/DPI*25.4/10:.1f} x {fh/DPI*25.4/10:.1f} cm  ({fw}x{fh}px)")

    page_w, page_h = mm2px(LETTER_W_MM), mm2px(LETTER_H_MM)
    usable_w = page_w - 2 * mm2px(PAGE_MARGIN_MM)
    usable_h = page_h - 2 * mm2px(PAGE_MARGIN_MM)

    cols = int(np.ceil(fw / usable_w))
    rows = int(np.ceil(fh / usable_h))
    tile_w = int(np.ceil(fw / cols))
    tile_h = int(np.ceil(fh / rows))
    print(f"Tiling: {cols} cols x {rows} rows = {cols*rows} Letter pages")

    pages = []
    for r in range(rows):
        for c in range(cols):
            y0, x0 = r * tile_h, c * tile_w
            tile = full[y0:y0 + tile_h, x0:x0 + tile_w]
            # pad ragged last row/col to full tile size (white)
            th, tw = tile.shape[:2]
            if th < tile_h or tw < tile_w:
                tile = cv2.copyMakeBorder(tile, 0, tile_h - th, 0, tile_w - tw,
                                          cv2.BORDER_CONSTANT, value=(255, 255, 255))

            page = np.full((page_h, page_w, 3), 255, np.uint8)
            ox = (page_w - tile_w) // 2
            oy = (page_h - tile_h) // 2
            page[oy:oy + tile_h, ox:ox + tile_w] = tile

            # Crop marks at the tile boundary (cut here, then butt to neighbours).
            m = mm2px(6)
            blk = (0, 0, 0)
            for (px, py, dx, dy) in [(ox, oy, 1, 1), (ox + tile_w, oy, -1, 1),
                                     (ox, oy + tile_h, 1, -1),
                                     (ox + tile_w, oy + tile_h, -1, -1)]:
                cv2.line(page, (px, py), (px + dx * m, py), blk, 2)
                cv2.line(page, (px, py), (px, py + dy * m), blk, 2)

            label = f"R{r+1}C{c+1}  (of {rows}x{cols})  -- print 100%, cut on marks, butt to neighbours"
            cv2.putText(page, label, (ox, oy - mm2px(3)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, blk, 1, cv2.LINE_AA)
            pages.append(Image.fromarray(cv2.cvtColor(page, cv2.COLOR_BGR2RGB)))

    from occ.paths import CALIB_ACTIVE
    out_dir = CALIB_ACTIVE
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "big_charuco_tiled.pdf"
    pages[0].save(pdf_path, "PDF", resolution=DPI, save_all=True,
                  append_images=pages[1:])
    prev = out_dir / "big_charuco_preview.png"
    cv2.imwrite(str(prev), cv2.resize(full, None, fx=0.25, fy=0.25))

    import json
    (out_dir / "board_measured_large.json").write_text(json.dumps({
        "_comment": "LARGE tiled board for extrinsics. RE-MEASURE the printed 100mm ruler and a square; update square_len_m/marker_len_m before using.",
        "squares_x": 8, "squares_y": 6, "dict_name": "DICT_5X5_100",
        "nominal_square_mm": 66.0, "nominal_marker_mm": 49.0,
        "square_len_m": 0.066, "marker_len_m": 0.049,
    }, indent=2))

    print(f"\nWrote {pdf_path}  ({len(pages)} pages)")
    print(f"Wrote {prev}")
    print("Print the PDF at 100% (actual size), trim on crop marks, butt tiles, "
          "mount flat & rigid, then MEASURE the 100mm ruler.")


if __name__ == "__main__":
    main()
