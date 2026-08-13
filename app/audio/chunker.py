"""Chunk PCM audio for HTTP streaming responses."""

import math

import numpy as np

DEFAULT_CHUNK_MS = 200
DEFAULT_PCM_FRAME = 2  # 16-bit


def chunk_audio(audio: np.ndarray, sample_rate: int, chunk_ms: int = DEFAULT_CHUNK_MS) -> list[np.ndarray]:
    if chunk_ms <= 0 or sample_rate <= 0:
        return [audio] if len(audio) else []
    chunk_samples = max(1, int(sample_rate * chunk_ms / 1000))
    n_chunks = max(1, math.ceil(len(audio) / chunk_samples))
    if n_chunks <= 1:
        return [audio] if len(audio) else []
    chunks = []
    for i in range(n_chunks):
        start = i * chunk_samples
        end = min(len(audio), start + chunk_samples)
        if end > start:
            chunks.append(audio[start:end])
    return chunks


def audio_chunk_bytes(audio: np.ndarray) -> bytes:
    return (np.clip(audio, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
