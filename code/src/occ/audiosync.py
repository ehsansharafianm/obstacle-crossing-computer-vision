"""Audio-based camera sync via a shared clap (or any sharp shared transient).

Two consumer cameras started by hand have an arbitrary time offset. A single
loud clap at the start of the take appears as a sharp spike in BOTH audio
tracks; cross-correlating the audio envelopes recovers the offset to the
millisecond. This is far more robust than inferring the offset from marker
motion (the rigid-foot method), and crucially it does NOT require the clap to
be visible in frame -- cameras aimed at the floor still record the sound.

Needs `imageio-ffmpeg` (bundles a static ffmpeg binary; no system install).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import numpy as np

try:
    import imageio_ffmpeg
    _FF = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    _FF = None


def _extract_audio(video, sr=16000, dur=None):
    """Decode a clip's audio to mono float at `sr` Hz. Returns x or None.

    `dur` (seconds) limits extraction to the opening window -- the clap lives
    there, and excluding the rest keeps repeated footstep/box-step sounds from
    diluting the correlation.
    """
    if _FF is None:
        return None
    from scipy.io import wavfile
    tmp = Path(tempfile.gettempdir()) / f"_occ_{Path(video).stem}_{sr}.wav"
    cmd = [_FF, "-y", "-v", "error"]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += ["-i", str(video), "-vn", "-ac", "1", "-ar", str(sr), "-f", "wav", str(tmp)]
    subprocess.run(cmd, capture_output=True)
    if not tmp.exists() or tmp.stat().st_size < 1000:
        return None
    _sr, x = wavfile.read(tmp)
    try:
        os.remove(tmp)
    except OSError:
        pass
    x = x.astype(np.float64)
    if x.ndim > 1:
        x = x.mean(1)
    return x


def _envelope(x, sr, win=0.005):
    from scipy.signal import fftconvolve
    e = np.abs(x)
    n = max(1, int(win * sr))
    e = fftconvolve(e, np.ones(n) / n, mode="same")
    return e / (e.max() + 1e-9)


def clap_offset(video1, video2, sr=16000, window=25.0):
    """Camera sync offset from a shared clap.

    Returns (off, confidence) where `off` (seconds) is defined so that a cam1
    time `t` corresponds to cam2 time `t - off` -- the convention the trajectory
    builder uses (it samples cam2 at ``grid - off``). Equivalently
    ``off = t_clap_cam1 - t_clap_cam2``.

    The clap is the loudest, most isolated transient in each clip's opening
    `window` seconds; the offset is the difference of the two peak times, located
    to ~1 audio sample (sub-millisecond -- far finer than a 1/240 s video frame).
    Confidence is how far each peak stands above its ambient baseline (a real clap
    is many x; ambient noise ~1). We do NOT global-cross-correlate the envelopes:
    with several loud sounds in a take (clap + box-drop + footsteps) that locks
    onto the wrong alignment. Returns (None, 0.0) if audio can't be read.
    """
    x1 = _extract_audio(video1, sr, dur=window)
    x2 = _extract_audio(video2, sr, dur=window)
    if x1 is None or x2 is None:
        return None, 0.0
    e1 = _envelope(x1, sr)
    e2 = _envelope(x2, sr)
    k1, k2 = int(np.argmax(e1)), int(np.argmax(e2))

    # isolation: how far each clap peak stands above its own ambient level
    # (mean envelope outside a +-0.3 s guard around the peak).
    def isolation(e, k):
        g = int(0.3 * sr)
        mask = np.ones(len(e), bool)
        mask[max(0, k - g):k + g] = False
        return float(e[k] / (e[mask].mean() + 1e-9))

    off = (k1 - k2) / sr            # cam1 time t <-> cam2 time (t - off)
    conf = min(isolation(e1, k1), isolation(e2, k2))
    return off, conf
