"""Content-type and mime helpers for audio formats."""

from typing import Optional

MIME_MAP = {
    "pcm": "audio/pcm",
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "flac": "audio/flac",
    "aac": "audio/aac",
}

EXT_MAP = {
    "pcm": "pcm",
    "wav": "wav",
    "mp3": "mp3",
    "opus": "ogg",
    "flac": "flac",
    "aac": "aac",
}


def mime_for(fmt: str) -> str:
    return MIME_MAP.get(fmt.lower(), "application/octet-stream")


def extension_for(fmt: str) -> str:
    return EXT_MAP.get(fmt.lower(), "bin")
