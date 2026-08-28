"""Build 3D trajectories for the 6-marker study set: two feet (left & right,
each toe+heel) plus two static ground markers. Adapts build_foot_trajectory to
several markers. Reads sessions/<id>/cam1.* + cam2.*, writes the CSV + plot there.

Usage (from code/):  python scripts/build_multi_trajectory.py 7
"""
import csv
import sys
import time
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.calibration import Intrinsics  # noqa: E402
from occ.stereo import StereoExtrinsics  # noqa: E402
from occ.reconstruct import triangulate_stereo, triangulate_nview, reprojection_error  # noqa: E402
from occ.tracking import detect_two_feet_ground  # noqa: E402
from occ.filtering import clean_trajectory  # noqa: E402
from occ.worldframe import WorldTransform  # noqa: E402
from occ.audiosync import clap_offset, clap_envelope  # noqa: E402

EXP_ROOT = Path("sessions")
VIDEO_EXTS = (".MOV", ".mov", ".MP4", ".mp4", ".avi", ".AVI")
# Recording-mode factor, auto-detected per session from the clip's reported fps:
#   NORMAL 60 fps  -> SLOWMO=1 (file time == real time, audio at real speed)
#   1/4 SLOW-MO    -> SLOWMO=4 (stores 120 fps real as ~30 fps, audio slowed 4x)
# The pipeline multiplies the file fps by SLOWMO for real time, divides the clap
# offset by SLOWMO, and tracks every SLOWMO-th frame (~30-60 Hz either way).
SLOWMO = 4                                   # set by detect_slowmo() in main()
FEET = ["L_toe", "L_heel", "R_toe", "R_heel"]
PAIRS = [("L_toe", "L_heel"), ("R_toe", "R_heel")]
COLORS = {"L_toe": "#7C3AED", "L_heel": "#22A559", "R_toe": "#D6336C", "R_heel": "#1098AD"}


def detect_slowmo(video):
    """1 for normal (~60 fps) recording, 4 for 1/4 slow-mo (~30 fps file)."""
    cap = cv2.VideoCapture(str(video))
    f = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return 1 if f >= 45 else 4


def find_cam_video(folder, cam):
    hits = sorted(p for p in folder.glob(f"{cam}*") if p.is_file())
    for ext in VIDEO_EXTS:
        for p in hits:
            if p.suffix == ext:
                return p
    return hits[0] if hits else None


def track(video):
    """Track markers at the grid rate (every SLOWMO-th real frame). Uses grab() to
    skip-decode the frames we don't score. Each foot = the CLOSEST toe/heel pair
    (clutter-safe: a same-coloured background object with no partner is ignored).
    ts is in REAL seconds."""
    cap = cv2.VideoCapture(str(video))
    fps = (cap.get(cv2.CAP_PROP_FPS) or 30.0) * SLOWMO
    ts, F, G = [], {k: [] for k in FEET}, []
    idx = 0
    while True:
        if not cap.grab():
            break
        if idx % SLOWMO == 0:
            ok, f = cap.retrieve()
            if not ok:
                break
            d = detect_two_feet_ground(f)
            ts.append(idx / fps)
            for k in FEET:
                F[k].append(d[k] if d[k] is not None else (np.nan, np.nan))
            G.append(d["ground"])
        idx += 1
    cap.release()
    return np.array(ts), {k: np.array(F[k], float) for k in FEET}, G


def load_or_track(video, cache_path):
    """Track, caching the 2D detections keyed by the clip's mtime so re-runs skip
    the slow decode. Delete the *_track_cache.npz to force a fresh track."""
    mt = video.stat().st_mtime
    if cache_path.exists():
        z = np.load(cache_path, allow_pickle=True)
        if float(z["mtime"]) == mt:
            F = {k: z[f"F_{k}"] for k in FEET}
            return z["ts"], F, list(z["G"]), True
    ts, F, G = track(video)
    np.savez(cache_path, ts=ts, G=np.array(G, dtype=object), mtime=mt,
             **{f"F_{k}": F[k] for k in FEET})
    return ts, F, G, False


def motion_offset(ts1, F1, ts2, F2, max_off=6.0, rate=60.0):
    """Data-driven camera sync: find the time shift that best aligns the two
    cameras' foot-marker PRESENCE (crossings happen at the same real instant in
    both). Returns (offset_s such that cam2 + off = cam1, score) or (None, 0)."""
    tmax = min(ts1[-1], ts2[-1]); dt = 1.0 / rate
    g = np.arange(0.0, tmax, dt)

    def presence(ts, F):
        p = np.zeros(len(g))
        for k in FEET:
            good = ~np.isnan(F[k][:, 0])
            if good.any():
                j = np.clip(np.searchsorted(g, ts[good]), 0, len(g) - 1)
                p[j] += 1.0
        return p

    p1 = presence(ts1, F1); p2 = presence(ts2, F2)
    if p1.sum() < 3 or p2.sum() < 3:
        return None, 0.0
    p1 -= p1.mean(); p2 -= p2.mean()
    smax = int(max_off / dt); best = None
    for s in range(-smax, smax + 1):
        if s >= 0:
            a, b = p1[s:], p2[:len(p2) - s]
        else:
            a, b = p1[:len(p1) + s], p2[-s:]
        if len(a) < rate:                                # need >=1 s of overlap
            continue
        score = float(np.dot(a, b)) / len(a)
        if best is None or score > best[0]:
            best = (score, s)
    return best[1] * dt, best[0]


def interp(ts, track, q, max_gap=0.08):    # bridge short detection flicker
    out = np.full((len(q), 2), np.nan)
    good = ~np.isnan(track[:, 0])
    if good.sum() >= 2:
        tg = ts[good]
        for a in range(2):
            out[:, a] = np.interp(q, tg, track[good, a], np.nan, np.nan)
        j = np.clip(np.searchsorted(tg, q), 1, len(tg) - 1)
        out[np.minimum(q - tg[j - 1], tg[j] - q) > max_gap] = np.nan
    return out


def ground_2d(G):
    """Two static red ground markers as their MEDIAN 2D position over frames where
    exactly two were seen, each frame's pair sorted left->right by x for a
    consistent order. Returns (2, 2) or None."""
    twos = [np.array(fr, float)[np.argsort(np.array(fr, float)[:, 0])]
            for fr in G if len(fr) == 2]
    if len(twos) < 3:
        return None
    return np.median(np.stack(twos), axis=0)


def write_audiosync(folder, tid, cams_audio, slowmo, say, ds_hz=200):
    """Save an audio-sync figure and return a DataFrame of the clap envelopes for
    ALL cameras (for MATLAB). `cams_audio` is a list of (label, ev, off) where off
    is the shift that aligns that camera to cam1's timeline (cam1's off = 0)."""
    import pandas as pd
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    colors = ["#1f77b4", "#d6336c", "#2ca02c", "#e6a010"]
    claps = [ev["clap_t"] / slowmo for _, ev, _ in cams_audio]
    tmax = max(claps) + 3.0
    fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    for i, (lab, ev, off) in enumerate(cams_audio):
        t = ev["t"] / slowmo; c = ev["clap_t"] / slowmo; col = colors[i % len(colors)]
        ax[0].plot(t, ev["env"], color=col, lw=1.0, label=f"{lab} (clap @ {c:.2f}s)")
        ax[0].axvline(c, color=col, ls="--", lw=1)
        ax[1].plot(t + off, ev["env"], color=col, lw=1.0,
                   label=(f"{lab} shifted {off:+.2f}s" if off else lab))
    ax[0].set_title(f"{tid}: audio energy — clap jumps BEFORE alignment ({len(cams_audio)} cameras)")
    ax[0].set_ylabel("energy"); ax[0].legend(fontsize=8); ax[0].set_xlim(0, tmax)
    ax[1].axvline(claps[0], color="k", ls="--", lw=1)
    ax[1].set_title("AFTER alignment — all claps line up")
    ax[1].set_xlabel("time (s, real)"); ax[1].set_ylabel("energy"); ax[1].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(folder / f"{tid}_audiosync.png", dpi=110); plt.close(fig)
    # common real-time grid for MATLAB: raw + aligned envelope per camera
    g = np.arange(0.0, tmax, 1.0 / ds_hz)
    cols = {"time_s": np.round(g, 4)}
    for lab, ev, off in cams_audio:
        t = ev["t"] / slowmo
        cols[f"{lab}_env"] = np.round(np.interp(g, t, ev["env"], np.nan, np.nan), 4)
        cols[f"{lab}_env_aligned"] = np.round(np.interp(g, t + off, ev["env"], np.nan, np.nan), 4)
    say(f"Audio-sync figure -> {tid}_audiosync.png  ({len(cams_audio)} cameras, clap jumps + alignment)")
    return pd.DataFrame(cols)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: build_multi_trajectory.py <test id>")
    raw = sys.argv[1]
    tid = f"test{int(raw):02d}" if str(raw).isdigit() else raw
    folder = EXP_ROOT / tid
    folder.mkdir(parents=True, exist_ok=True)
    cam1 = find_cam_video(folder, "cam1")
    cam2 = find_cam_video(folder, "cam2")
    if cam1 is None or cam2 is None:
        raise SystemExit(f"[{tid}] need cam1/cam2 clips in {folder.resolve()}")

    t_start = time.perf_counter()
    log = [f"Test: {tid}", ""]

    def say(m=""):
        print(m); log.append(m)

    global SLOWMO
    SLOWMO = detect_slowmo(cam1)
    say(f"Recording mode: {'normal (~60 fps)' if SLOWMO == 1 else 'slow-mo 1/4 (120 fps real)'}")

    intr1 = Intrinsics.load("calibration/intrinsics_cam1.npz")
    intr2 = Intrinsics.load("calibration/intrinsics_cam2.npz")
    extr = StereoExtrinsics.load("calibration/stereo_extrinsics.npz")
    R, T = extr.R, extr.t.reshape(3, 1)

    # Projection matrices in cam1's normalised frame (P = [R|t], no K).
    P1n = np.hstack([np.eye(3), np.zeros((3, 1))])
    P2n = np.hstack([extr.R, extr.t.reshape(3, 1)])
    # Optional 3rd camera: compose cam3->cam1 through the cam2<->cam3 calibration.
    cam3 = find_cam_video(folder, "cam3")
    intr3 = P3n = None
    c23_path = Path("calibration/stereo_extrinsics_cam2cam3.npz")
    if cam3 is not None and c23_path.exists():
        intr3 = Intrinsics.load("calibration/intrinsics_cam3.npz")
        e23 = StereoExtrinsics.load(c23_path)            # cam3 relative to cam2
        R31 = e23.R @ extr.R                             # X_c3 = R_b(R_a X + t_a) + t_b
        t31 = (e23.R @ extr.t.reshape(3, 1)) + e23.t.reshape(3, 1)
        P3n = np.hstack([R31, t31])
    elif cam3 is not None:
        cam3 = None                                      # clip present but not calibrated

    def tri_robust(pts, Ps):
        """N-view triangulation that drops a single disagreeing view. With 3
        cameras a bad detection in one (e.g. the slightly noisier cam3) would
        otherwise corrupt the least-squares point; if the worst view's normalised
        reprojection error is a clear outlier, re-triangulate without it."""
        X = triangulate_nview(pts, Ps)
        if len(pts) >= 3:
            errs = [reprojection_error(X, [p], [P]) for p, P in zip(pts, Ps)]
            w = int(np.argmax(errs))
            if errs[w] > max(0.004, 2.5 * float(np.median(errs))):   # ~0.004 norm ≈ 6 px
                keep = [i for i in range(len(pts)) if i != w]
                X = triangulate_nview([pts[i] for i in keep], [Ps[i] for i in keep])
        return X

    def norm_pts(intr, pix):
        """Undistort tracked pixel points to normalised coords (NaN preserved)."""
        out = np.full((len(pix), 2), np.nan)
        good = ~np.isnan(pix[:, 0])
        if good.any():
            out[good] = cv2.undistortPoints(
                pix[good].reshape(-1, 1, 2).astype(np.float64),
                intr.camera_matrix, intr.dist_coeffs).reshape(-1, 2)
        return out

    def tri(p1, p2):
        X = triangulate_stereo(p1.reshape(1, 2), p2.reshape(1, 2),
                               intr1.camera_matrix, intr1.dist_coeffs,
                               intr2.camera_matrix, intr2.dist_coeffs, R, T)
        return X[0]

    def match_reds(c1, c2):
        """Match the two static red obstacle markers across cameras by geometry
        (lowest triangulation reprojection error), NOT by floor height -- they
        sit at different heights on the obstacle. Returns (2, 3) in cam-1 frame."""
        n1 = cv2.undistortPoints(c1.reshape(-1, 1, 2).astype(np.float64),
                                 intr1.camera_matrix, intr1.dist_coeffs).reshape(-1, 2)
        n2 = cv2.undistortPoints(c2.reshape(-1, 1, 2).astype(np.float64),
                                 intr2.camera_matrix, intr2.dist_coeffs).reshape(-1, 2)
        P1 = np.hstack([np.eye(3), np.zeros((3, 1))]); P2 = np.hstack([R, T])
        best = None
        for perm in ([0, 1], [1, 0]):
            Xs, err = [], 0.0
            for i in range(2):
                Xh = cv2.triangulatePoints(P1, P2, n1[i].reshape(2, 1), n2[perm[i]].reshape(2, 1))
                X = (Xh[:3] / Xh[3]).ravel(); Xs.append(X)
                for P, n in ((P1, n1[i]), (P2, n2[perm[i]])):
                    p = P @ np.append(X, 1.0); p = p[:2] / p[2]
                    err += float(np.hypot(p[0] - n[0], p[1] - n[1]))
            if best is None or err < best[0]:
                best = (err, np.array(Xs))
        return best[1]

    def timed_track(cam, tag):
        t0 = time.perf_counter()
        ts, F, G, cached = load_or_track(cam, folder / f"{tid}_{tag}_track_cache.npz")
        say(f"[{tid}] {cam.name} ({tag}): {'loaded cache' if cached else 'tracked'} "
            f"in {time.perf_counter()-t0:.1f}s")
        return ts, F, G

    ts1, F1, G1 = timed_track(cam1, "cam1")
    ts2, F2, G2 = timed_track(cam2, "cam2")
    ts3 = F3 = G3 = None
    if cam3 is not None:
        ts3, F3, G3 = timed_track(cam3, "cam3")
        say(f"[{tid}] 3-camera mode")
    for k in FEET:
        c3s = f"  cam3 {100*np.mean(~np.isnan(F3[k][:,0])):.0f}%" if cam3 is not None else ""
        say(f"  {k:7s} cam1 {100*np.mean(~np.isnan(F1[k][:,0])):.0f}%  "
            f"cam2 {100*np.mean(~np.isnan(F2[k][:,0])):.0f}%{c3s}")

    # --- Camera sync via the RIGID-SHOE constraint (robust to a weak clap) -----
    # The true offset makes each rigid shoe's toe-heel distance most constant, so
    # we scan offsets for the minimum toe-heel scatter (among high-overlap ones).
    # This is decisive where the clap is quiet (low confidence) or the motion sync
    # locks onto a false periodic peak. Clap/motion are logged for reference.
    grid = ts1                                            # cam1 timeline (real s)

    def rigidity(offB, refTs, refF, tsB, FB, tri_pair, refOff=0.0, stride=2):
        q = grid[::stride]; stds = []; ntot = 0
        for toe, heel in PAIRS:
            P = {}
            for k in (toe, heel):
                a = interp(refTs, refF[k], q - refOff); b = interp(tsB, FB[k], q - offB)
                X = np.full((len(q), 3), np.nan)
                for i in np.where(~np.isnan(a[:, 0]) & ~np.isnan(b[:, 0]))[0]:
                    X[i] = tri_pair(a[i], b[i])
                P[k] = X
            d = np.linalg.norm(P[toe] - P[heel], axis=1) * 1000
            d = d[~np.isnan(d)]; ntot += len(d)
            if len(d) >= 5:
                md = np.median(d); d2 = d[np.abs(d - md) < 100]
                if len(d2) >= 5:
                    stds.append(np.std(d2))
        return (float(np.mean(stds)) if stds else 1e9), ntot

    def pick_offset(refTs, refF, tsB, FB, tri_pair, refOff=0.0, seeds=()):
        # Candidate offsets: any seeds (clap/motion -- crucial when the true offset
        # is outside the coarse window, e.g. cameras started >9 s apart) plus a
        # coarse global scan. Then refine around the best (max overlap, min scatter).
        a = (refTs, refF, tsB, FB, tri_pair, refOff)
        cand = [s for s in seeds if s is not None] + list(np.arange(-9.0, 9.01, 0.5))
        scored = [(o, *rigidity(o, *a)) for o in cand]
        nmax = max((c[2] for c in scored), default=0) or 1
        good = [c for c in scored if c[2] >= 0.4 * nmax and c[1] < 1e8] or scored
        o0 = min(good, key=lambda c: c[1])[0]
        best = None
        for o in np.arange(o0 - 0.4, o0 + 0.4, 0.02):
            s, n = rigidity(o, *a)
            if n >= 0.4 * nmax and (best is None or s < best[0]):
                best = (s, o)
        return best[1], best[0]

    ev1 = clap_envelope(cam1); ev2 = clap_envelope(cam2)
    off_clap = (ev1["clap_t"] / SLOWMO - ev2["clap_t"] / SLOWMO) if (ev1 and ev2) else None
    off_mot, _ = motion_offset(ts1, F1, ts2, F2)
    if off_clap is not None:
        say(f"Clap: cam1 @ {ev1['clap_t']/SLOWMO:.3f}s (x{ev1['prominence']:.0f}), "
            f"cam2 @ {ev2['clap_t']/SLOWMO:.3f}s (x{ev2['prominence']:.0f})  -> cam2 {off_clap:+.3f}s")
    if off_mot is not None:
        say(f"Motion candidate: cam2 {off_mot:+.3f}s")
    off, off_std = pick_offset(ts1, F1, ts2, F2, tri, seeds=(off_clap, off_mot))  # cam2 vs cam1
    tag = "  [clap agrees]" if (off_clap is not None and abs(off - off_clap) < 0.3) else "  [clap OFF]"
    say(f"-> cam2 sync: {off:+.3f}s = cam1   (toe-heel scatter {off_std:.0f} mm){tag}")

    off3 = None; ev3 = None
    if cam3 is not None:
        def tri23(p2, p3):                                  # CLEAN cam2<->cam3 pose
            return triangulate_stereo(p2.reshape(1, 2), p3.reshape(1, 2),
                                      intr2.camera_matrix, intr2.dist_coeffs,
                                      intr3.camera_matrix, intr3.dist_coeffs,
                                      e23.R, e23.t.reshape(3, 1))[0]
        ev3 = clap_envelope(cam3)
        c3clap = (ev1["clap_t"] / SLOWMO - ev3["clap_t"] / SLOWMO) if (ev1 and ev3) else None
        if ev3 is not None:
            say(f"Clap: cam3 @ {ev3['clap_t']/SLOWMO:.3f}s (x{ev3['prominence']:.0f})  -> cam3 {c3clap:+.3f}s")
        # Sync cam3 against cam2 through the CLEAN cam2<->cam3 pair, SEEDED by the
        # cam3 clap (its true offset can be well outside the coarse window when the
        # cameras started many seconds apart). off3 stays relative to cam1's grid.
        off3, off3_std = pick_offset(ts2, F2, ts3, F3, tri23, refOff=off, seeds=(c3clap,))
        tag3 = "  [clap agrees]" if (c3clap is not None and abs(off3 - c3clap) < 0.3) else "  [clap OFF]"
        say(f"-> cam3 sync: {off3:+.3f}s = cam1   (cam2+cam3 scatter {off3_std:.0f} mm){tag3}")

    # --- Audio-sync figure + data for ALL cameras (clap jumps + alignment) -----
    audio_df = None
    if ev1 is not None and ev2 is not None:
        cams_audio = [("cam1", ev1, 0.0), ("cam2", ev2, off)]
        if ev3 is not None and off3 is not None:
            cams_audio.append(("cam3", ev3, off3))
        audio_df = write_audiosync(folder, tid, cams_audio, SLOWMO, say)

    W_path = Path("calibration/world_transform.npz")
    W = WorldTransform.load(W_path) if W_path.exists() else None

    # Camera list for n-view reconstruction: (ts, detections, intrinsics, proj, offset).
    cams = [(ts1, F1, intr1, P1n, 0.0), (ts2, F2, intr2, P2n, off)]
    if cam3 is not None and off3 is not None:
        cams.append((ts3, F3, intr3, P3n, off3))
    say(f"Reconstructing from {len(cams)} cameras (marker needs >=2 to get a 3D point)")

    world = {}
    n_clean, n_gap = 0, 0                                 # clean cam1+cam2 vs cam3 gap-fill
    for k in FEET:
        # per camera: normalised, time-aligned 2D points on the common grid
        NP = [norm_pts(intr, interp(ts, Fk[k], grid - o)) for (ts, Fk, intr, _P, o) in cams]
        Pmats = [P for (_ts, _F, _intr, P, _o) in cams]
        X = np.full((len(grid), 3), np.nan)
        for i in range(len(grid)):
            have = [c for c in range(len(cams)) if not np.isnan(NP[c][i, 0])]
            if len(have) < 2:
                continue
            # cam1+cam2 is the precision core: it has the WIDEST baseline (~1.98 m
            # vs cam2<->cam3's ~1.11 m), and triangulation precision scales with
            # baseline -- so despite cam2<->cam3 having lower calibration RMS, the
            # cam1+cam2 pair reconstructs tighter. cam3 fills gaps where cam1/cam2 miss.
            if 0 in have and 1 in have:
                use = [0, 1]; n_clean += 1
            else:
                use = have; n_gap += 1
            X[i] = tri_robust([NP[c][i] for c in use], [Pmats[c] for c in use])
        world[k] = W.apply(X) if W is not None else X
    if cam3 is not None:
        say(f"  reconstructed points: {n_clean} from cam1+cam2 (wide baseline), {n_gap} gap-filled with cam3")

    # per-foot rigid-pair filter + plausibility gate
    for toe, heel in PAIRS:
        d = np.linalg.norm(world[toe] - world[heel], axis=1)
        med = np.nanmedian(d); mad = np.nanmedian(np.abs(d - med)) + 1e-9
        bad = ~np.isnan(d) & (np.abs(d - med) > max(0.04, 4 * mad))
        world[toe][bad] = np.nan; world[heel][bad] = np.nan
        say(f"  {toe[0]} foot: toe-heel {med*1000:.0f} mm, dropped {int(bad.sum())} outliers")
    for k in FEET:
        Z = world[k][:, 2]
        bad = ~np.isnan(Z) & ((Z < -0.10) | (Z > 1.5) |
                              (np.abs(world[k][:, 0]) > 3) | (np.abs(world[k][:, 1]) > 3))
        world[k][bad] = np.nan

    # --- Obstacle markers: two static reds at ANY height -> 2 fixed 3D points --
    ground_w = None
    c1 = ground_2d(G1); c2 = ground_2d(G2)
    if c1 is not None and c2 is not None:
        pts = match_reds(c1, c2)                     # geometry match (not floor-bound)
        ground_w = W.apply(pts) if W is not None else pts
        say(f"Obstacle markers (world, mm): "
            + " | ".join(f"({p[0]*1000:.0f},{p[1]*1000:.0f},Z={p[2]*1000:.0f})" for p in ground_w))

    fps = 1 / np.median(np.diff(grid))
    for k in FEET:
        world[k] = clean_trajectory(world[k], fps)
    frame_label = "world frame (Z = height above floor)" if W is not None else "camera-1 frame"
    say(f"Output: {frame_label}")
    for k in FEET:
        say(f"  {k:7s} {100*np.mean(~np.isnan(world[k][:,0])):.0f}% reconstructed")

    # --- Excel output: one .xlsx, sheet "markers" (feet, per-frame) + "ground" -
    import pandas as pd
    cols = {"time_s": np.round(grid, 4)}
    for k in FEET:
        for a, axname in enumerate("xyz"):
            cols[f"{k}_{axname}_mm"] = np.round(world[k][:, a] * 1000, 2)
    df_markers = pd.DataFrame(cols)
    xlsx_path = folder / f"{tid}_trajectory.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        df_markers.to_excel(xw, sheet_name="markers", index=False)
        if ground_w is not None:
            pd.DataFrame({
                "marker": [f"ground{i+1}" for i in range(len(ground_w))],
                "x_mm": np.round(ground_w[:, 0] * 1000, 2),
                "y_mm": np.round(ground_w[:, 1] * 1000, 2),
                "z_mm": np.round(ground_w[:, 2] * 1000, 2),
            }).to_excel(xw, sheet_name="ground", index=False)
        if audio_df is not None:                         # clap-sync envelopes (MATLAB)
            audio_df.to_excel(xw, sheet_name="audio", index=False)

    # --- Plot -----------------------------------------------------------------
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(11, 8))
    for k in FEET:
        ax[0].plot(grid, world[k][:, 2] * 1000, color=COLORS[k], lw=1.3, label=k)
    ax[0].set_title(f"{tid}: marker HEIGHT over time  (both feet)")
    ax[0].set_xlabel("time (s)"); ax[0].set_ylabel("height Z (mm)"); ax[0].legend(fontsize=8, ncol=4)
    for toe, heel in PAIRS:
        d = np.linalg.norm(world[toe] - world[heel], axis=1) * 1000
        ax[1].plot(grid, d, lw=1.0, label=f"{toe[0]} foot toe-heel  (std {np.nanstd(d):.0f} mm)")
    ax[1].set_title("Toe-heel distance per foot (rigid shoe -> flat)")
    ax[1].set_xlabel("time (s)"); ax[1].set_ylabel("mm"); ax[1].legend(fontsize=9)
    fig.tight_layout(); fig.savefig(folder / f"{tid}_trajectory.png", dpi=110)

    say(f"\nSaved {xlsx_path.name} (sheets: markers"
        + (" + ground" if ground_w is not None else "") + f"), {tid}_trajectory.png")

    elapsed = time.perf_counter() - t_start
    mins, secs = divmod(elapsed, 60)
    say(f"Processing time: {int(mins)} min {secs:.1f} s  ({elapsed:.1f} s total)")
    (folder / f"{tid}_run.txt").write_text("\n".join(log) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
