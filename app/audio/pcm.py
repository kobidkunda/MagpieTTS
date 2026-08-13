"""PCM helpers. Native model output is 22.05 kHz mono 16-bit PCM."""

import wave
import io

import numpy as np


def to_int16(audio: np.ndarray) -> np.ndarray:
    a = np.asarray(audio, dtype=np.float32)
    if a.ndim == 2:
        a = a.mean(axis=0)
    a = np.clip(a, -1.0, 1.0)
    return (a * 32767.0).astype(np.int16)


def pcm_bytes(audio: np.ndarray) -> bytes:
    return to_int16(audio).tobytes()


def wav_from_pcm(pcm: bytes, sample_rate: int, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def pcm_from_wav(wav_bytes: bytes) -> tuple[np.ndarray, int, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        sr = wf.getframerate()
        ch = wf.getnchannels()
        frames = wf.readframes(wf.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    return audio, sr, ch


def duration_s(pcm: bytes, sample_rate: int) -> float:
    return len(pcm) / 2.0 / sample_rate if sample_rate else 0.0
