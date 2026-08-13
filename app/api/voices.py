"""Voices + languages API."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.state import get_state
from app.text.language import LANGUAGE_NAMES, SUPPORTED_LANGUAGES

router = APIRouter(prefix="/api", tags=["Voices & Languages"])


@router.get("/voices", summary="List voices with full metadata")
async def voices():
    st = get_state()
    return {"object": "list", "data": st.config.get("voices", [])}


@router.get("/languages", summary="List languages supported by the loaded model")
async def languages():
    return {
        "object": "list",
        "data": [
            {"id": code, "name": LANGUAGE_NAMES.get(code, code)}
            for code in SUPPORTED_LANGUAGES
        ],
    }
