"""Native Magpie adapter: the full-control request path."""

from typing import Optional

from app.api.common import synthesize_request
from app.schemas.speech import NativeTTSRequest


def synthesize_native(req: NativeTTSRequest) -> dict:
    cfg = req.cfg
    return synthesize_request(
        text=req.text,
        language=req.language,
        voice=req.speaker,
        response_format=req.audio.format,
        sample_rate=req.audio.sample_rate,
        apply_tn=req.text_normalization,
        cfg_enabled=cfg.enabled if cfg else True,
        cfg_scale=cfg.scale if cfg else 2.5,
        priority=req.priority,
        mode=req.mode,
    )
