"""Audio encoder: PCM -> wav/mp3/opus/flac/aac.

Uses PyAV/FFmpeg when available, falls back to built-in WAV encoder only.
"""

import io
import logging
import subprocess

import numpy as np

from app.audio.pcm import to_int16, wav_from_pcm
from app.schemas.errors import ApiException, ErrorCodes

logger = logging.getLogger("magpie.audio.encoder")

SUPPORTED_FORMATS = ("pcm", "wav", "mp3", "opus", "flac", "aac")

_av = None


def init() -> None:
    global _av
    try:
        import av
        _av = av
        logger.info("audio encoder backend: PyAV")
    except Exception:
        _av = None
        logger.warning("PyAV not available; only PCM/WAV output supported until ffmpeg is installed")


def _has_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=10)
        return True
    except Exception:
        return False


def encode_pcm(audio: np.ndarray, fmt: str, sample_rate: int) -> bytes:
    """Encode float audio [-1, 1] into the requested format bytes."""
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise ApiException(ErrorCodes.INVALID_FORMAT,
                           f"Unsupported format '{fmt}'. Allowed: {', '.join(SUPPORTED_FORMATS)}.",
                           details={"allowed": list(SUPPORTED_FORMATS)})
    if fmt == "opus" and sample_rate not in (8000, 12000, 16000, 24000, 48000):
        from app.audio.resampler import resample
        src_rate = sample_rate
        sample_rate = 24000 if src_rate <= 24000 else 48000
        audio = resample(audio, src_rate, sample_rate)
    pcm = to_int16(audio)
    if fmt == "pcm":
        return pcm.tobytes()
    if fmt == "wav":
        return wav_from_pcm(pcm.tobytes(), sample_rate)

    if _av is not None:
        try:
            return _av_encode(pcm.tobytes(), fmt, sample_rate)
        except Exception as e:
            logger.warning("PyAV encode failed for %s: %s", fmt, e)

    if _has_ffmpeg():
        try:
            return _ffmpeg_encode(pcm.tobytes(), fmt, sample_rate)
        except Exception as e:
            logger.warning("ffmpeg encode failed for %s: %s", fmt, e)

    raise ApiException(ErrorCodes.ENCODER_FAILED,
                       f"Encoder for '{fmt}' is unavailable. Install PyAV or FFmpeg.",
                       retryable=False)


def _av_encode(pcm: bytes, fmt: str, sample_rate: int) -> bytes:
    import av
    codec_name = {"mp3": "libmp3lame", "opus": "libopus", "flac": "flac", "aac": "aac"}[fmt]
    container_fmt = fmt if fmt in ("mp3", "opus") else "flac" if fmt == "flac" else "adts"
    out = io.BytesIO()
    with av.open(out, "w", format=container_fmt) as container:
        stream = container.add_stream(codec_name, rate=sample_rate)
        stream.layout = "mono"
        stream.format = "s16"
        if fmt == "opus":
            stream.bit_rate = 64000
        elif fmt == "mp3":
            stream.bit_rate = 128000
        elif fmt == "aac":
            stream.bit_rate = 128000
        pcm_arr = np.frombuffer(pcm, dtype=np.int16)
        frame_len = 4096
        for start in range(0, len(pcm_arr), frame_len):
            chunk = pcm_arr[start:start + frame_len]
            if len(chunk) == 0:
                continue
            frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
            frame.sample_rate = sample_rate
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    return out.getvalue()


def _ffmpeg_encode(pcm: bytes, fmt: str, sample_rate: int) -> bytes:
    codecs = {"mp3": "libmp3lame", "opus": "libopus", "flac": "flac", "aac": "aac"}
    containers = {"mp3": "mp3", "opus": "ogg", "flac": "flac", "aac": "adts"}
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "-i", "pipe:0",
        "-c:a", codecs[fmt], "-f", containers[fmt], "pipe:1",
    ]
    proc = subprocess.run(cmd, input=pcm, capture_output=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode(errors="replace"))
    return proc.stdout
