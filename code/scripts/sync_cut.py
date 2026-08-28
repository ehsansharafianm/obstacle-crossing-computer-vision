"""Cut each camera clip in a session so they all START the same time before the
CLAP -- producing time-aligned videos you can review side-by-side (or drop into a
presentation). Uses the same clap detector as the trajectory pipeline.

These clips are ONLY for manual/visual review -- the 3D analysis always runs on the
ORIGINAL files. The aligned clips are written to  sessions/<id>/synced_videos/  and
each begins `pre` seconds before the clap, so the clap lands at the same position in
all of them and they play in lock-step.

Runs automatically at the end of build_multi_trajectory; can also be run alone:
    python scripts/sync_cut.py 10          # 2 s before the clap (default)
    python scripts/sync_cut.py 10 1.5      # 1.5 s before the clap
"""
import subprocess
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from occ.audiosync import clap_envelope, _FF  # noqa: E402

EXP_ROOT = Path("sessions")
VIDEO_EXTS = (".MOV", ".mov", ".MP4", ".mp4", ".avi", ".AVI")
OUT_SUBDIR = "synced_videos"


def detect_slowmo(video):
    cap = cv2.VideoCapture(str(video))
    f = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return 1 if f >= 45 else 4                     # normal 60 fps vs 1/4 slow-mo


def find_cam(folder, cam):
    hits = sorted(p for p in folder.glob(f"{cam}*")
                  if p.is_file() and p.suffix in VIDEO_EXTS and "synced" not in p.stem)
    return hits[0] if hits else None


def cut_session(folder, pre=2.0, crf=20, log=print, force=False):
    """Write clap-aligned review clips for a session into folder/synced_videos/.
    Reads only the ORIGINAL clips; never touched by the analysis. Skips a camera
    whose synced clip already exists (delete it or pass force=True to redo)."""
    if _FF is None:
        log("  sync_cut: ffmpeg not available -- skipped"); return 0
    out_dir = Path(folder) / OUT_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    for cam in ("cam1", "cam2", "cam3"):
        v = find_cam(Path(folder), cam)
        if v is None:
            continue
        out = out_dir / f"{cam}_synced.mp4"
        if out.exists() and not force:
            log(f"  {cam}: {OUT_SUBDIR}/{out.name} already exists -- kept"); done += 1; continue
        ev = clap_envelope(v)
        if ev is None:
            log(f"  {cam}: could not find clap -- skipped"); continue
        sm = detect_slowmo(v)                      # cut point is in the clip's own time
        start = max(0.0, ev["clap_t"] - pre * sm)  # clap_t and start are file seconds
        # -ss before -i with re-encode = accurate seek; keep audio so the clap is audible.
        cmd = [_FF, "-y", "-ss", f"{start:.3f}", "-i", str(v),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
               "-c:a", "aac", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0 and out.exists():
            log(f"  {cam}: clap @ {ev['clap_t']:.2f}s -> {OUT_SUBDIR}/{out.name}"); done += 1
        else:
            log(f"  {cam}: ffmpeg failed\n{r.stderr[-300:]}")
    log(f"  {done} aligned review clip(s) -> {out_dir}")
    return done


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: sync_cut.py <test id> [seconds-before-clap]")
    raw = sys.argv[1]
    tid = f"test{int(raw):02d}" if str(raw).isdigit() else raw
    pre = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    folder = EXP_ROOT / tid
    if not folder.is_dir():
        raise SystemExit(f"no session folder: {folder.resolve()}")
    print(f"[{tid}] aligning clips to start {pre:.1f}s before the clap")
    cut_session(folder, pre=pre, force=True)       # explicit run -> always redo


if __name__ == "__main__":
    main()
