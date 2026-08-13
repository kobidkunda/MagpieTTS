"""VoxCPM compatibility adapter (ISOLATED).

The exact Voice Translate -> VoxCPM request contract will be integrated later;
only this adapter gets updated then. The Magpie engine itself never changes.
"""

from typing import Optional

from app.api.common import synthesize_request


def voxcpm_request_contract(
    text: str,
    speaker: str = "Aria",
    language: str = "en",
    format: str = "wav",
    sample_rate: int = 16000,
    **kwargs,
) -> dict:
    """Map a VoxCPM-style request to the Magpie pipeline.

    VoxCPM servers commonly expose /api/v1/tts-style endpoints with
    {text, speaker, lang, format, sample_rate}. Map them here.
    """
    return synthesize_request(
        text=text,
        language=language,
        voice=speaker,
        response_format=format,
        sample_rate=sample_rate,
        apply_tn=True,
        priority=10,
    )


def voxcpm_aliases() -> list[str]:
    """Endpoints the VoxCPM adapter can answer (registered separately when the
    Voice Translate contract is finalized)."""
    return ["/api/voxcpm/tts"]
