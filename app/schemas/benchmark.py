"""Benchmark schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class BenchmarkRequest(BaseModel):
    profile: str = "fp16-realtime"
    concurrent_users: int = Field(default=1, ge=1, le=8)
    language: str = "en"
    iterations: int = Field(default=10, ge=1, le=100)
    streaming: bool = False
    texts: Optional[List[str]] = None


class BenchmarkResult(BaseModel):
    profile: str
    language: str
    concurrent_users: int
    iterations: int
    streaming: bool
    ttfa_p50_ms: float
    ttfa_p95_ms: float
    ttfa_p99_ms: float
    rtf: float
    peak_vram_mb: float
    avg_vram_mb: float
    gpu_util_pct: float
    gpu_temp_c: float
    requests_per_sec: float
    audio_duration_s: float
    failures: int
    error_codes: List[str] = []
