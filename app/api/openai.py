"""OpenAI-compatible audio API.

POST /v1/audio/speech  (OpenAI-shaped payload)
POST /v1/audio/speech (stream)
POST /v1/audio/cancel
"""

import logging

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.common import synthesize_request
from app.audio.chunker import audio_chunk_bytes, chunk_audio
from app.audio.formats import mime_for
from app.audio.pcm import to_int16
from app.schemas.errors import ErrorCodes
from app.schemas.speech import OpenAISpeechRequest
from app.state import get_state
from app.utils.common import new_request_id

logger = logging.getLogger("magpie.api.openai")
router = APIRouter(prefix="/v1", tags=["OpenAI-compatible"])

VALID_MODELS = {"magpie-tts-multilingual-357m", "magpie-tts-multilingual-364m", "magpie-tts"}


@router.post("/audio/speech", summary="Synthesize speech (OpenAI-compatible)",
             description="Accepts the OpenAI audio/speech payload shape. "
                         "Authorization header is accepted but never validated.",
             response_class=Response)
async def audio_speech(req: OpenAISpeechRequest, request: Request):
    request_id = getattr(request.state, "request_id", None) or new_request_id()
    if req.model not in VALID_MODELS:
        return JSONResponse(status_code=404, content={
            "error": {
                "code": "INVALID_REQUEST", "message": f"Unknown model '{req.model}'.",
                "type": "invalid_request_error", "request_id": request_id,
                "retryable": False,
                "details": {"allowed": sorted(VALID_MODELS)}}})

    fmt = (req.response_format or "wav").lower()
    stream_format = (req.stream_format or fmt).lower()

    if req.stream:
        return await _stream_response(req, stream_format, request_id)

    res = synthesize_request(
        text=req.input,
        language=req.language,
        voice=req.voice,
        response_format=fmt,
        speed=req.speed,
        sample_rate=req.sample_rate,
        apply_tn=req.text_normalization if req.text_normalization is not None else False,
        cfg_enabled=req.cfg_enabled,
        cfg_scale=req.cfg_scale or 2.5,
        priority=10,
        mode=req.mode or "auto",
    )
    st = get_state()
    st.stats.record(ttfa_ms=res["ttfa_ms"], gen_ms=res["generation_ms"],
                    rtf=res["rtf"], duration_s=res["duration_s"])
    return Response(content=res["audio"], media_type=mime_for(fmt),
                    headers={"X-Request-ID": res["request_id"]})


async def _stream_response(req: OpenAISpeechRequest, stream_format: str, request_id: str):
    import asyncio
    import numpy as np

    st = get_state()

    def _synthesize():
        return synthesize_request(
            text=req.input, language=req.language, voice=req.voice,
            response_format="pcm", speed=req.speed, sample_rate=None,
            apply_tn=req.text_normalization if req.text_normalization is not None else False,
            cfg_enabled=req.cfg_enabled, cfg_scale=req.cfg_scale or 2.5,
            priority=10, mode=req.mode or "auto")

    def _wav_header(data_size: int, sample_rate: int) -> bytes:
        import struct
        byte_rate = sample_rate * 2
        return (b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
                + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, byte_rate, 2, 16)
                + b"data" + struct.pack("<I", data_size))

    async def gen():
        try:
            res = await asyncio.get_event_loop().run_in_executor(None, _synthesize)
            rate = res["sample_rate"]
            audio = np.frombuffer(res["audio"], dtype=np.int16).astype(np.float32) / 32767.0
            chunks = chunk_audio(audio, rate, chunk_ms=200)
            if stream_format == "wav":
                pcm = to_int16(audio).tobytes()
                first = True
                for c in chunks:
                    chunk = audio_chunk_bytes(c)
                    if first:
                        yield _wav_header(len(pcm), rate) + chunk
                        first = False
                    else:
                        yield chunk
            elif stream_format == "pcm":
                for c in chunks:
                    yield audio_chunk_bytes(c)
            else:
                from app.audio import encoder as audio_encoder
                yield audio_encoder.encode_pcm(audio, stream_format, rate)
        except Exception as e:
            logger.warning("stream aborted: %s", e)

    return StreamingResponse(gen(), media_type=mime_for(stream_format),
                             headers={"X-Request-ID": request_id, "X-Accel-Buffering": "no"})


@router.post("/audio/cancel", summary="Cancel active and queued synthesis",
             description="Cancels all queued/pending synthesis jobs (barge-in support).")
async def cancel(request: Request):
    st = get_state()
    n = st.scheduler.cancel()
    st.stats.record(cancelled=True)
    return JSONResponse(content={"object": "audio.cancel", "cancelled": n, "status": "ok"})


@router.get("/audio/list_voices", summary="NVIDIA-style voice list",
            include_in_schema=True)
@router.get("/audio/voices", summary="List available voices")
async def list_voices():
    st = get_state()
    voices = []
    for v in st.config.get("voices", []):
        voices.append({
            "id": v["id"],
            "name": v["name"],
            "speaker_index": v["speaker_index"],
            "gender": v.get("gender"),
            "default": v.get("default", False),
        })
    return {"object": "list", "data": voices}
