"""Model discovery API (OpenAI /v1/models compatible)."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.state import get_state
from app.utils.common import new_request_id

router = APIRouter(prefix="/v1", tags=["Models"])


@router.get("/models", summary="List models",
            description="OpenAI-compatible model listing with load state.")
async def list_models(request: Request):
    request_id = getattr(request.state, "request_id", None) or new_request_id()
    st = get_state()
    mm = st.model_manager
    status = mm.status()
    data = [{
        "id": status["model_id"],
        "object": "model",
        "owned_by": "nvidia",
        "loaded": status["state"] == "active",
        "profile": status["profile"],
        "precision": status["precision"],
        "device": status["device"],
        "revision": status["revision"],
        "state": status["state"],
    }]
    return JSONResponse(content={"object": "list", "data": data},
                        headers={"X-Request-ID": request_id})


@router.get("/models/{model_id}", summary="Get one model")
async def get_model(model_id: str, request: Request):
    st = get_state()
    mm = st.model_manager
    status = mm.status()
    if model_id != status["model_id"] and model_id not in (
            "magpie-tts-multilingual-364m", "magpie-tts"):
        return JSONResponse(status_code=404, content={"error": {
            "code": "INVALID_REQUEST", "message": f"Model '{model_id}' not found.",
            "type": "invalid_request_error",
            "request_id": getattr(request.state, "request_id", None) or new_request_id(),
            "retryable": False}})
    return JSONResponse(content={
        "id": status["model_id"],
        "object": "model",
        "owned_by": "nvidia",
        "loaded": status["state"] == "active",
        "profile": status["profile"],
        "precision": status["precision"],
        "device": status["device"],
        "revision": status["revision"],
    }, headers={"X-Request-ID": getattr(request.state, "request_id", None) or new_request_id()})
