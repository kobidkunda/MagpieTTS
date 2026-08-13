"""Native Magpie API with full advanced controls.

POST /api/tts/generate
GET  /api/tts/pronunciation  (list)
POST /api/tts/pronunciation (upsert)
DELETE /api/tts/pronunciation
POST /api/tts/pronunciation/test
"""

import logging

from fastapi import APIRouter, Body, Request, Response
from fastapi.responses import JSONResponse

from app.api.common import synthesize_request
from app.audio.formats import mime_for
from app.schemas.errors import ErrorCodes
from app.schemas.speech import NativeTTSRequest
from app.state import get_state
from app.text.ipa_dictionary import IPADictionary
from app.utils.common import new_request_id

logger = logging.getLogger("magpie.api.native")
router = APIRouter(prefix="/api/tts", tags=["Native Magpie"])


@router.post("/generate", summary="Advanced native synthesis",
             description="Exposes full Magpie controls: profile, CFG, "
                         "text normalization, audio options, priority, mode.")
async def generate(req: NativeTTSRequest, request: Request):
    request_id = getattr(request.state, "request_id", None) or new_request_id()
    st = get_state()

    cfg = req.cfg or type("C", (), {"enabled": False, "scale": 2.5})()
    text = req.text
    ipa = st.ipa.apply(text, req.language) if st.ipa else text

    res = synthesize_request(
        text=ipa,
        language=req.language,
        voice=req.speaker,
        response_format=req.audio.format,
        speed=1.0,
        sample_rate=req.audio.sample_rate,
        apply_tn=req.text_normalization,
        cfg_enabled=cfg.enabled,
        cfg_scale=cfg.scale,
        priority=min(30, max(0, req.priority)),
        mode=req.mode,
        profile=None if req.profile == "fp16-realtime" else req.profile,
    )
    st.stats.record(ttfa_ms=res["ttfa_ms"], gen_ms=res["generation_ms"],
                    rtf=res["rtf"], duration_s=res["duration_s"])
    return Response(content=res["audio"], media_type=mime_for(res["format"]),
                    headers={"X-Request-ID": res["request_id"]})


@router.get("/pronunciation", summary="List pronunciation dictionary entries")
async def list_pronunciation():
    st = get_state()
    return {"object": "list", "data": st.ipa.list()}


@router.post("/pronunciation", summary="Add or update a pronunciation entry")
async def upsert_pronunciation(entry: dict = Body(...)):
    word = entry.get("word", "").strip()
    if not word:
        return JSONResponse(status_code=422, content={"error": {
            "code": ErrorCodes.INVALID_REQUEST, "message": "word is required",
            "type": "validation_error", "retryable": False}})
    st = get_state()
    return st.ipa.upsert(word, entry.get("language", "en"),
                         entry.get("ipa", ""), entry.get("enabled", True))


@router.delete("/pronunciation/{word}", summary="Delete a pronunciation entry")
async def delete_pronunciation(word: str, language: str = "en"):
    st = get_state()
    ok = st.ipa.delete(word, language)
    if not ok:
        return JSONResponse(status_code=404, content={"error": {
            "code": ErrorCodes.INVALID_REQUEST,
            "message": f"No entry for '{word}' ({language}).",
            "type": "not_found", "retryable": False}})
    return {"status": "deleted", "word": word, "language": language}


@router.post("/pronunciation/test", summary="Synthesize a word with the dictionary applied")
async def test_pronunciation(payload: dict = Body(...), request: Request = None):
    word = payload.get("word", "").strip()
    language = payload.get("language", "en")
    ipa = payload.get("ipa")
    st = get_state()
    if ipa:
        st.ipa.upsert(word, language, ipa, True)
    text = st.ipa.apply(word, language)
    res = synthesize_request(text=text, language=language, voice="aria",
                             response_format="wav", priority=20)
    return Response(content=res["audio"], media_type="audio/wav",
                    headers={"X-Request-ID": res["request_id"]})
