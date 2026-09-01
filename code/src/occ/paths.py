"""Single source of truth for where data lives on disk.

Layout (all anchored to the repo root, so scripts work from any CWD):

    <repo>/
      videos/                      raw video only (git-ignored, heavy)
        sessions/testNN/             cam1.mp4, cam2.mp4, cam3.mp4
        calibration/calibNN/         cam*_ext.*, cam*_floor.*
      results/                     everything generated (tracked in git)
        sessions/testNN/             xlsx, png, run.txt, *_track_cache.npz, synced_videos/
        calibration/active/          intrinsics_*.npz, active extrinsics/world .npz, board specs
        calibration/calibNN/         per-calibration result .npz + calib_run.txt

Raw videos and generated results are deliberately kept apart (videos are huge and
git-ignored; results are small and versioned).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]      # occ -> src -> code -> repo root
VIDEOS = ROOT / "videos"
RESULTS = ROOT / "results"
CALIB_ACTIVE = RESULTS / "calibration" / "active"   # inputs the pipeline READS every run


def session_videos(tid):
    """Folder holding a recording session's raw cam clips."""
    return VIDEOS / "sessions" / tid


def session_results(tid):
    """Folder for a recording session's generated outputs."""
    return RESULTS / "sessions" / tid


def calib_videos(cid):
    """Folder holding a calibration session's raw board clips."""
    return VIDEOS / "calibration" / cid


def calib_results(cid):
    """Folder for a calibration session's generated .npz + run log."""
    return RESULTS / "calibration" / cid
