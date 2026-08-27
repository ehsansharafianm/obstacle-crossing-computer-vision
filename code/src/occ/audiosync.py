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


def clap_envelope(video, sr=8000, window=90.0, smooth=0.15, thr_mult=5.0):
    """Detect the clap as the FIRST prominent energy hump in a clip's opening
    `window` seconds, and return the audio envelope for plotting.

    Returns dict with:
      t         : envelope time axis (seconds, CLIP time base)
      env       : smoothed energy envelope, normalised to its own max
      clap_t    : time of the detected clap (seconds, CLIP time base)
      prominence: clap height over the ambient median (real clap ~10-20x)
    or None if the audio can't be read.

    "First prominent hump" (not global max) is deliberate: in a real take there
    may be louder sounds LATER (a dropped box, a shout). As long as the clap is
    the first thing well above ambient, we lock onto it and ignore the rest.
    """
    x = _extract_audio(video, sr, dur=window)
    if x is None:
        return None
    e = _envelope(x, sr, smooth)
    t = np.arange(len(e)) / sr
    med = float(np.median(e)) + 1e-9
    above = np.where(e > med * thr_mult)[0]
    if len(above):
        first = above[0]
        seg = e[first:first + int(0.5 * sr)]           # peak of that first hump
        k = first + int(np.argmax(seg))
    else:
        k = int(np.argmax(e))                          # fallback: global max
    return {"t": t, "env": e, "clap_t": k / sr, "prominence": float(e[k] / med)}


def clap_offset(video1, video2, sr=16000, window=90.0, smooth=0.15):
    """Camera sync offset from a shared clap -- robust to slow-motion audio.

    Returns (off, confidence) where `off` (seconds, in the CLIP's own time base)
    is defined so a cam1 time `t` corresponds to cam2 time `t - off` -- the
    convention the trajectory builder uses. Equivalently
    ``off = t_clap_cam1 - t_clap_cam2``. For ¼-speed slow-mo the clips (and this
    offset) run 4x slow, so the caller divides by that factor to get real seconds.

    The clap is the single dominant energy HUMP in each clip's opening `window`
    seconds. Two things make this work where a sharp-spike detector fails on
    slow-motion audio:
      * `window` is large -- hand-started cameras can differ by many seconds, so
        the same clap lands at very different positions in each file (e.g. 12 s
        vs 43 s). Too small a window misses it in the later-started clip.
      * `smooth` is broad (~0.15 s) -- slow-mo stretches a 20 ms clap into a
        ~100 ms hump, so we smooth to that scale and take the hump's peak instead
        of hunting for a spike that no longer exists.
    Confidence is the hump's prominence over the ambient median (a real clap is
    many x; footsteps ~1-2x). Returns (None, 0.0) if audio can't be read.
    """
    r1 = clap_envelope(video1, sr=8000, window=window, smooth=smooth)
    r2 = clap_envelope(video2, sr=8000, window=window, smooth=smooth)
    if r1 is None or r2 is None:
        return None, 0.0
    off = r1["clap_t"] - r2["clap_t"]   # cam1 time t <-> cam2 time (t - off)
    conf = min(r1["prominence"], r2["prominence"])
    return off, conf
