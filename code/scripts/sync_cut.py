"""Cut each camera clip in a session so they all START the same time before the
CLAP -- producing time-aligned videos you can review side-by-side (or drop into a
presentation). Uses the same clap detector as the trajectory pipeline, so the cut
matches the sync used for the 3D results.

Each output `<cam>_synced.mp4` begins `pre` seconds before the clap, so the clap
lands at the same position in all of them and the clips play in lock-step.

Usage (from code/):
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


def detect_slowmo(video):
    cap = cv2.VideoCapture(str(video))
    f = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.release()
    return 1 if f >= 45 else 4                     # normal 60 fps vs 1/4 slow-mo


def find_cam(folder, cam):
    hits = sorted(p for p in folder.glob(f"{cam}*")
                  if p.is_file() and p.suffix in VIDEO_EXTS and "synced" not in p.stem)
    return hits[0] if hits else None


def main():
    if _FF is None:
        raise SystemExit("ffmpeg not available (need imageio-ffmpeg).")
    if len(sys.argv) < 2:
        raise SystemExit("usage: sync_cut.py <test id> [seconds-before-clap]")
    raw = sys.argv[1]
    tid = f"test{int(raw):02d}" if str(raw).isdigit() else raw
    pre = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    folder = EXP_ROOT / tid
    if not folder.is_dir():
        raise SystemExit(f"no session folder: {folder.resolve()}")

    print(f"[{tid}] aligning clips to start {pre:.1f}s before the clap")
    done = 0
    for cam in ("cam1", "cam2", "cam3"):
        v = find_cam(folder, cam)
        if v is None:
            continue
        ev = clap_envelope(v)
        if ev is None:
            print(f"  {cam}: could not read audio / find clap -- skipped")
            continue
        sm = detect_slowmo(v)                      # cut point is in the clip's own time
        start = max(0.0, ev["clap_t"] - pre * sm)  # clap_t and start are file seconds
        out = folder / f"{cam}_synced.mp4"
        # -ss before -i with re-encode = accurate seek; keep audio so the clap is audible.
        cmd = [_FF, "-y", "-ss", f"{start:.3f}", "-i", str(v),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
               "-c:a", "aac", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            print(f"  {cam}: ffmpeg failed\n{r.stderr[-400:]}")
            continue
        print(f"  {cam}: clap @ {ev['clap_t']:.2f}s -> cut from {start:.2f}s -> {out.name}")
        done += 1
    print(f"Done. {done} aligned clip(s) written -> {folder.resolve()}\n"
          f"They all start {pre:.1f}s before the clap, so they play in lock-step.")


if __name__ == "__main__":
    main()
