"""Request/response schemas for the OpenAI-compatible and native TTS APIs."""

from typing import Optional

from pydantic import BaseModel, Field


class OpenAISpeechRequest(BaseModel):
    model: str = Field(default="magpie-tts-multilingual-357m",
                       description="Model identifier. Must match the loaded model.")
    input: str = Field(..., min_length=1,
                       description="Text to synthesize (UTF-8).")
    voice: str = Field(default="aria", description="One of: aria, jason, john, leo, sofia.")
    language: str = Field(default="en", description="Language code (ar, zh, en, fr, de, hi, it, ja, ko, pt, es, vi).")
    response_format: str = Field(default="wav",
                                 description="pcm, wav, mp3, opus, flac, aac")
    speed: float = Field(default=1.0, ge=0.25, le=4.0,
                         description="Speech speed multiplier.")
    instructions: Optional[str] = Field(default=None, description="Accepted for compatibility; unused.")
    stream: Optional[bool] = Field(default=False, description="Stream audio chunks via chunked transfer.")
    stream_format: Optional[str] = Field(default=None, description="Format per streamed chunk (defaults to response_format).")
    sample_rate: Optional[int] = Field(default=None, description="Output sample rate. Defaults to 22050.")
    mode: Optional[str] = Field(default="auto", description="auto | standard | long")
    cfg_enabled: Optional[bool] = Field(default=None, description="Classifier-free guidance override.")
    cfg_scale: Optional[float] = Field(default=None, description="CFG scale.")
    text_normalization: Optional[bool] = Field(default=False, description="Apply text normalization.")


class NativeTTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: str = Field(default="en")
    speaker: str = Field(default="Aria", description="Aria, Jason, John, Leo, Sofia")
    profile: str = Field(default="fp16-realtime")
    text_normalization: bool = False
    cfg: Optional["CFGConfig"] = None
    audio: "AudioConfig" = Field(default_factory=lambda: AudioConfig())
    stream: bool = False
    priority: int = Field(default=10, ge=0, le=30)
    mode: str = Field(default="auto")


class CFGConfig(BaseModel):
    enabled: bool = True
    scale: float = 2.5


class AudioConfig(BaseModel):
    format: str = "wav"
    sample_rate: int = 22050


class SynthesisResult(BaseModel):
    audio: bytes
    format: str
    sample_rate: int
    channels: int = 1
    duration_s: float
    text_len: int
    ttfa_ms: Optional[float] = None
    generation_ms: Optional[float] = None
    rtf: Optional[float] = None
    peak_vram_mb: Optional[float] = None
    request_id: str


NativeTTSRequest.model_rebuild()
