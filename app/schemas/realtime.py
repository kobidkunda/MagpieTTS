"""WebSocket realtime protocol schemas (OpenAI/NVIDIA-style events)."""

from typing import Any, Optional, Dict

from pydantic import BaseModel, Field


class RealtimeSessionConfig(BaseModel):
    voice: str = "aria"
    language: str = "en"
    format: str = "pcm"
    sample_rate: int = 22050
    speed: float = 1.0
    text_normalization: bool = False
    cfg_enabled: bool = True
    cfg_scale: float = 2.5
    priority: int = 0
    mode: str = "auto"
    phrase: Optional[Dict[str, Any]] = None


class RealtimeEvent(BaseModel):
    type: str
    session: Optional[RealtimeSessionConfig] = None
    text: Optional[str] = None
    event_id: Optional[str] = None
    response_id: Optional[str] = None
    error: Optional[Dict[str, Any]] = None


def server_event(type_: str, **kwargs) -> dict:
    evt = {"type": type_, **kwargs}
    if "session_id" not in evt and "response_id" not in evt:
        evt["session_id"] = kwargs.get("session_id")
    return evt
