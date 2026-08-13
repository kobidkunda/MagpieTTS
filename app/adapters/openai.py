"""OpenAI SDK adapter: maps OpenAI speech payloads to the native pipeline."""

from typing import Optional

from app.api.common import synthesize_request


def openai_to_native(payload: dict) -> dict:
    """Convert an OpenAI /v1/audio/speech payload to native params."""
    return {
        "text": payload["input"],
        "language": payload.get("language", "en"),
        "voice": payload.get("voice", "aria"),
        "response_format": payload.get("response_format", "wav"),
        "speed": float(payload.get("speed", 1.0)),
        "sample_rate": payload.get("sample_rate"),
        "apply_tn": payload.get("text_normalization", False),
        "cfg_enabled": payload.get("cfg_enabled"),
        "cfg_scale": payload.get("cfg_scale", 2.5),
        "priority": 10,
        "mode": payload.get("mode", "auto"),
    }


def synthesize_openai(payload: dict, priority: int = 10) -> dict:
    return synthesize_request(**openai_to_native(payload), priority=priority)
