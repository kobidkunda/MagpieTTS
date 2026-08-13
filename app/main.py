"""Magpie TTS Server - FastAPI application factory.

Single worker, single process, one persistent model.
Serves: REST API, WebSocket realtime, Swagger, ReDoc, and the built GUI.
"""

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import admin, models, native, openai, realtime, system, voices
from app.audio import encoder as audio_encoder
from app.audio import resampler as audio_resampler
from app.runtime import health
from app.runtime.gpu_monitor import init as gpu_init
from app.schemas.errors import ApiException, api_exception_handler
from app.state import AppState
from app.utils.common import RequestStats, new_request_id
from app.utils.logging_setup import setup_logging
from app.utils.middleware import RequestContextMiddleware

logger = logging.getLogger("magpie.main")

WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "web", "dist")


def create_app(config_path: Optional[str] = None, load_model: bool = True) -> FastAPI:
    from app.state import get_state

    st = get_state()
    if config_path and st.config_path != config_path:
        st.config_path = config_path
    st.stats = RequestStats()
    st.config["log_file"] = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "logs", "server.log")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        setup_logging(level=st.config["logging"]["level"],
                      max_bytes=st.config["logging"]["max_log_bytes"],
                      backups=st.config["logging"]["backups"],
                      log_text=st.config["logging"].get("log_customer_text", False))
        health.set_http_alive(True)
        audio_resampler.init()
        audio_encoder.init()
        gpu_init(st.config["runtime"]["device"])
        st.start()
        logger.info("Magpie TTS server starting: %s:%s (workers=1)",
                    st.config["server"]["host"], st.config["server"]["port"])
        if load_model:
            threading.Thread(target=_boot_model, args=(st,), daemon=True,
                             name="model-boot").start()
        yield
        health.set_http_alive(False)
        st.shutdown()

    app = FastAPI(
        title="Magpie TTS Server",
        description=(
            "Standalone Magpie 357M multilingual realtime TTS API server. "
            "OpenAI-compatible REST (/v1/audio/speech), native Magpie REST "
            "(/api/tts/generate), and WebSocket realtime (/v1/realtime?intent=synthesize). "
            "No authentication. Bind: 0.0.0.0:8092. Single model process (workers=1)."),
        version=st.config["server"]["version"],
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    app.add_exception_handler(ApiException, api_exception_handler)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "Request validation failed.",
                "type": "validation_error",
                "request_id": new_request_id(),
                "retryable": False,
                "details": {"errors": exc.errors()},
            }})

    app.include_router(openai.router)
    app.include_router(native.router)
    app.include_router(models.router)
    app.include_router(voices.router)
    app.include_router(system.router)
    app.include_router(admin.router)
    app.include_router(realtime.router)

    _mount_gui(app)
    return app


def _boot_model(st: AppState) -> None:
    try:
        st.model_manager.load_default()
    except Exception as e:
        logger.exception("model boot failed: %s", e)
        health.set_model(False, error=str(e))


def _mount_gui(app: FastAPI) -> None:
    from fastapi.staticfiles import StaticFiles

    if not os.path.isdir(WEB_DIST):
        logger.warning("web/dist not found (%s); GUI disabled until frontend build.", WEB_DIST)
        return

    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="gui")


app = create_app()


def main() -> None:
    import uvicorn

    st = get_state()
    uvicorn.run("app.main:app", host=st.config["server"]["host"],
                port=int(st.config["server"]["port"]), workers=1,
                log_level="info")


if __name__ == "__main__":
    main()
