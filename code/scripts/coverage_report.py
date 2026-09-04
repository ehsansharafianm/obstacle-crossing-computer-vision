"""Coverage report for a processed session: where (in the world X/Y plane) did we
actually reconstruct foot markers? Use it to compare camera layouts -- run a short
walk, process it, then check how far the reconstructable volume reaches along Y
(the walk direction) and X (the obstacle line).

Usage (from code/):
    python scripts/coverage_report.py 22          # -> results/sessions/test22/
    python scripts/coverage_report.py test22

Prints the Y and X reconstructed ranges + an ASCII Y-histogram, and saves a figure
(<id>_coverage.png): a Y-histogram and a top-down X/Y coverage map.
"""
import sys
from pathlib import Path

import numpy as np
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.paths import session_results  # noqa: E402

FEET = ["L_toe", "L_heel", "R_toe", "R_heel"]
BIN = 0.25  # m


def load_feet(xlsx):
    wb = openpyxl.load_workbook(xlsx, read_only=True)
    rows = list(wb["markers"].values); hdr = rows[0]
    d = np.array([[np.nan if v is None else v for v in r] for r in rows[1:]], float)
    col = {h: i for i, h in enumerate(hdr)}
    X, Y, Z = [], [], []
    for m in FEET:
        if m + "_x_mm" not in col:
            continue
        x = d[:, col[m + "_x_mm"]]; y = d[:, col[m + "_y_mm"]]; z = d[:, col[m + "_z_mm"]]
        g = ~np.isnan(y)
        X.append(x[g]); Y.append(y[g]); Z.append(z[g])
    return (np.concatenate(X) / 1000, np.concatenate(Y) / 1000, np.concatenate(Z) / 1000)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: coverage_report.py <session id>   (e.g. 22 or test22)")
    raw = sys.argv[1]
    tid = f"test{int(raw):02d}" if str(raw).isdigit() else raw
    xlsx = session_results(tid) / f"{tid}_trajectory.xlsx"
    if not xlsx.exists():
        raise SystemExit(f"no trajectory xlsx: {xlsx}")

    X, Y, Z = load_feet(xlsx)
    print(f"[{tid}] reconstructed foot points: {len(Y)}")
    print(f"  Y (walk dir):     {Y.min():+.2f} .. {Y.max():+.2f} m   (span {Y.max()-Y.min():.2f} m)")
    print(f"  X (obstacle line):{X.min():+.2f} .. {X.max():+.2f} m   (span {X.max()-X.min():.2f} m)")

    lo = np.floor(Y.min() / BIN) * BIN; hi = np.ceil(Y.max() / BIN) * BIN
    edges = np.arange(lo, hi + BIN, BIN)
    h, _ = np.histogram(Y, bins=edges); mx = max(h.max(), 1)
    print("  Y coverage (points per 0.25 m bin):")
    for i in range(len(h)):
        print(f"   {edges[i]:+.2f}..{edges[i+1]:+.2f} : {'#'*int(h[i]/mx*40):40s} {h[i]}")

    # --- figure: Y-histogram + top-down X/Y coverage map ---
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    ax[0].bar((edges[:-1] + edges[1:]) / 2, h, width=BIN * 0.9, color="#2f7ed8")
    ax[0].set_xlabel("Y = walk direction (m)"); ax[0].set_ylabel("reconstructed foot points")
    ax[0].set_title(f"{tid}: coverage along the walk (Y)"); ax[0].grid(True, alpha=0.3)
    hb = ax[1].hexbin(Y, X, gridsize=40, cmap="viridis", mincnt=1)
    ax[1].set_xlabel("Y = walk direction (m)"); ax[1].set_ylabel("X = obstacle line (m)")
    ax[1].set_title(f"{tid}: top-down coverage map"); ax[1].set_aspect("equal", "box")
    fig.colorbar(hb, ax=ax[1], label="points")
    fig.tight_layout()
    out = session_results(tid) / f"{tid}_coverage.png"
    fig.savefig(out, dpi=120); plt.close(fig)
    print(f"  saved {out}")


if __name__ == "__main__":
    main()
