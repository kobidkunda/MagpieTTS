"""Resampler using torchaudio when available, numpy fallback otherwise.

Keeps native 22.05 kHz output and resamples to the requested rate.
"""

import logging

import numpy as np

from app.schemas.errors import ApiException, ErrorCodes

logger = logging.getLogger("magpie.audio.resampler")

_ffmpeg_resampler = None
_torchaudio = None


def init() -> None:
    global _ffmpeg_resampler, _torchaudio
    try:
        import torchaudio
        _torchaudio = torchaudio
        torchaudio.set_audio_backend("soundfile") if hasattr(torchaudio, "set_audio_backend") else None
        logger.info("resampler backend: torchaudio")
    except Exception:
        try:
            import ffmpeg
            _ffmpeg_resampler = ffmpeg
            logger.info("resampler backend: ffmpeg")
        except Exception:
            logger.warning("no torchaudio/ffmpeg; using numpy linear interpolation")


def _numpy_resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst:
        return audio
    n_out = int(round(len(audio) * dst / src))
    x = np.linspace(0, len(audio) - 1, n_out)
    return np.interp(x, np.arange(len(audio)), audio).astype(np.float32)


def _torchaudio_resample(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    import torch
    t = torch.from_numpy(np.asarray(audio, dtype=np.float32))[None, :]
    t = torchaudio.transforms.Resample(src, dst)(t)
    return t[0].numpy()


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if dst_rate <= 0:
        raise ApiException(ErrorCodes.INVALID_SAMPLE_RATE, f"Invalid sample rate {dst_rate}.")
    if src_rate == dst_rate:
        return np.asarray(audio, dtype=np.float32)
    try:
        if _torchaudio is not None:
            return _torchaudio_resample(audio, src_rate, dst_rate)
        if _ffmpeg_resampler is not None:
            return _ffmpeg_resample_audio(audio, src_rate, dst_rate)
        return _numpy_resample(audio, src_rate, dst_rate)
    except Exception as e:
        logger.warning("resampler error (%s), falling back to numpy: %s", type(e).__name__, e)
        return _numpy_resample(audio, src_rate, dst_rate)


def _ffmpeg_resample_audio(audio: np.ndarray, src: int, dst: int) -> np.ndarray:
    import subprocess
    pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16).tobytes()
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "s16le", "-ar", str(src), "-ac", "1", "-i", "pipe:0",
        "-f", "s16le", "-ar", str(dst), "-ac", "1", "pipe:1",
    ]
    proc = subprocess.run(cmd, input=pcm, capture_output=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace"))
    out = np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32767.0
    return out
