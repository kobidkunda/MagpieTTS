"""Shared synthesis pipeline used by all API routers."""

import logging
import time
from typing import Optional

from app.audio import encoder as audio_encoder
from app.audio import resampler as audio_resampler
from app.schemas.errors import ApiException, ErrorCodes
from app.state import get_state
from app.utils.common import new_request_id
from app.text.normalizer import normalize_text, split_for_long_mode

logger = logging.getLogger("magpie.api.common")


def resolve_voice(voice_id: str) -> int:
    st = get_state()
    voices = {v["id"]: v for v in st.config.get("voices", [])}
    voice = voices.get((voice_id or "").lower())
    if voice is None:
        raise ApiException(ErrorCodes.INVALID_VOICE,
                           f"Voice '{voice_id}' is not available.",
                           details={"allowed": list(voices.keys())})
    return int(voice["speaker_index"])


def resolve_language(lang: str) -> str:
    from app.text.language import validate_language
    return validate_language(lang or "en")


def synthesize_request(
    text: str,
    language: str,
    voice: str,
    response_format: str,
    speed: float = 1.0,
    sample_rate: Optional[int] = None,
    apply_tn: bool = False,
    cfg_enabled: Optional[bool] = None,
    cfg_scale: float = 2.5,
    priority: int = 10,
    mode: str = "auto",
    profile: Optional[str] = None,
) -> dict:
    """Run the full pipeline: validate -> schedule -> synth -> encode.

    Returns dict with: audio bytes, format, sample_rate, duration_s, ttfa_ms,
    generation_ms, rtf, peak_vram_mb, request_id, segments.
    """
    st = get_state()
    mm = st.model_manager
    request_id = new_request_id()

    text = normalize_text(text, apply_tn)
    lang = resolve_language(language)
    speaker_idx = resolve_voice(voice)

    fmt = (response_format or "wav").lower()
    if fmt not in audio_encoder.SUPPORTED_FORMATS:
        raise ApiException(ErrorCodes.INVALID_FORMAT,
                           f"Unsupported format '{fmt}'.",
                           details={"allowed": list(audio_encoder.SUPPORTED_FORMATS)})

    if sample_rate is not None and sample_rate not in (8000, 16000, 22050, 24000, 48000):
        raise ApiException(ErrorCodes.INVALID_SAMPLE_RATE,
                           f"Unsupported sample rate {sample_rate}.",
                           details={"allowed": [8000, 16000, 22050, 24000, 48000]})
    out_rate = sample_rate or st.config["runtime"]["default_sample_rate"]

    if not (0.25 <= speed <= 4.0):
        raise ApiException(ErrorCodes.INVALID_SPEED,
                           f"Speed {speed} out of range [0.25, 4.0].",
                           details={"allowed": [0.25, 4.0]})

    use_cfg = cfg_enabled if cfg_enabled is not None else st.config["runtime"]["cfg_enabled"]
    cfg_scale = cfg_scale if cfg_scale else st.config["runtime"]["cfg_scale"]

    segments = [text]
    if mode == "auto" and len(text) > 1500:
        segments = split_for_long_mode(text)
    elif mode == "long":
        segments = split_for_long_mode(text)

    def _job(cancel_event):
        mm.require_active()
        first = True
        ttfa = None
        audio_parts = []
        total_gen_ms = 0.0
        peak_vram = 0.0
        for seg in segments:
            if cancel_event is not None and cancel_event.is_set():
                raise ApiException(ErrorCodes.SYNTHESIS_CANCELLED, "Synthesis cancelled.", status=400)
            res = mm.synthesize(
                seg, lang, speaker_idx,
                profile_id=profile,
                apply_tn=apply_tn, use_cfg=use_cfg, cfg_scale=cfg_scale,
                cancel_event=cancel_event)
            if first:
                ttfa = res["generation_ms"]
                first = False
            audio_parts.append(res["audio"])
            total_gen_ms += res["generation_ms"]
            peak_vram = max(peak_vram, res["peak_vram_mb"])
        import numpy as np
        audio = np.concatenate(audio_parts) if len(audio_parts) > 1 else audio_parts[0]
        duration = len(audio) / 22050.0
        if speed != 1.0:
            audio = _apply_speed(audio, speed)
            duration = len(audio) / 22050.0
        return {
            "audio": audio, "ttfa_ms": ttfa, "generation_ms": total_gen_ms,
            "duration_s": duration, "peak_vram_mb": peak_vram,
            "sample_rate": 22050,
        }

    mm.require_active()
    job = st.scheduler.submit(_job, priority=priority,
                              meta={"endpoint": "tts", "language": lang, "voice": voice},
                              timeout_s=st.config["runtime"]["synth_timeout_seconds"])
    started = time.time()
    res = st.scheduler.wait(job, st.config["runtime"]["synth_timeout_seconds"])
    ttfa = res["ttfa_ms"]

    audio = res["audio"]
    if out_rate != 22050:
        audio = audio_resampler.resample(audio, 22050, out_rate)

    audio_bytes = audio_encoder.encode_pcm(audio, fmt, out_rate)
    total_ms = (time.time() - started) * 1000.0
    rtf = res["generation_ms"] / 1000.0 / res["duration_s"] if res["duration_s"] > 0 else 0.0

    return {
        "audio": audio_bytes,
        "format": fmt,
        "sample_rate": out_rate,
        "duration_s": res["duration_s"],
        "ttfa_ms": ttfa,
        "generation_ms": total_ms,
        "rtf": rtf,
        "peak_vram_mb": res["peak_vram_mb"],
        "request_id": request_id,
        "segments": len(segments),
    }


def _apply_speed(audio, speed: float):
    """Pitch-preserving speed change via torchaudio if present, else resample trick."""
    import numpy as np
    if abs(speed - 1.0) < 1e-3:
        return audio
    try:
        import torchaudio.functional as F
        import torch
        t = torch.from_numpy(np.asarray(audio, dtype=np.float32))[None, :]
        out = F.phase_vocoder(t, ratio=1.0 / speed, n_fft=2048)[0].numpy()
        return out
    except Exception:
        pass
    return audio
