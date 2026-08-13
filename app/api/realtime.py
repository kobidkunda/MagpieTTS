"""WebSocket realtime API: /v1/realtime?intent=synthesize

Lifecycle: session.created -> session.update -> input_text.append xN ->
input_text.commit -> audio.chunk xN -> response.completed
Client events: session.update, input_text.append, input_text.commit, response.cancel
Server events: session.created, session.updated, response.created, audio.chunk,
               response.completed, response.cancelled, error
"""

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.audio import encoder as audio_encoder
from app.audio import resampler as audio_resampler
from app.api.common import resolve_language, resolve_voice
from app.schemas.errors import ApiException, ErrorCodes
from app.schemas.realtime import RealtimeSessionConfig
from app.state import get_state
from app.text.phrase_buffer import PhraseBuffer
from app.utils.common import new_request_id, new_session_id

logger = logging.getLogger("magpie.api.realtime")
router = APIRouter(prefix="/v1", tags=["Realtime WebSocket"])


class RealtimeSession:
    def __init__(self, ws: WebSocket, request_id: str):
        self.id = new_session_id()
        self.ws = ws
        self.request_id = request_id
        self.cfg = RealtimeSessionConfig()
        self.buffer = PhraseBuffer()
        self._events: asyncio.Queue = asyncio.Queue()
        self._task: Optional[asyncio.Task] = None
        self._response_open = False
        self._last_chunk_ts = 0.0
        self._speaker_idx = 0

    def apply_config(self, payload: dict) -> None:
        self.cfg = RealtimeSessionConfig(**payload)
        self._speaker_idx = resolve_voice(self.cfg.voice)
        resolve_language(self.cfg.language)
        self.buffer = PhraseBuffer(
            min_words=int((self.cfg.phrase or {}).get("min_words", 3)),
            preferred_words=int((self.cfg.phrase or {}).get("preferred_words", 8)),
            max_words=int((self.cfg.phrase or {}).get("max_words", 18)),
            soft_timeout_ms=int((self.cfg.phrase or {}).get("soft_timeout_ms", 120)),
            hard_timeout_ms=int((self.cfg.phrase or {}).get("hard_timeout_ms", 250)),
        )

    async def send(self, event: dict) -> None:
        await self.ws.send_text(json.dumps(event, ensure_ascii=False))

    async def send_error(self, code: str, message: str, retryable: bool = False) -> None:
        await self.send({
            "type": "error",
            "error": {
                "code": code, "message": message, "retryable": retryable,
                "request_id": self.request_id, "session_id": self.id,
            },
        })


@router.websocket("/realtime")
async def realtime(ws: WebSocket, intent: str = "synthesize"):
    st = get_state()
    await ws.accept()
    sess = RealtimeSession(ws, getattr(ws, "request_id", None) or new_request_id())

    async def run_synthesis(text: str, ttfa_start: float):
        st2 = get_state()
        mm = st2.model_manager
        fmt = sess.cfg.format
        out_rate = sess.cfg.sample_rate
        if fmt not in audio_encoder.SUPPORTED_FORMATS:
            await sess.send_error(ErrorCodes.INVALID_FORMAT, f"Invalid format '{fmt}'.")
            return
        if out_rate not in (8000, 16000, 22050, 24000, 48000):
            await sess.send_error(ErrorCodes.INVALID_SAMPLE_RATE,
                                  f"Invalid sample rate {out_rate}.")
            return
        try:
            def _job(cancel_event):
                return mm.synthesize(
                    text, sess.cfg.language, sess._speaker_idx,
                    apply_tn=sess.cfg.text_normalization,
                    use_cfg=sess.cfg.cfg_enabled, cfg_scale=sess.cfg.cfg_scale,
                    cancel_event=cancel_event)

            job = st2.scheduler.submit(_job, priority=int(sess.cfg.priority),
                                       meta={"endpoint": "realtime", "session": sess.id})
            res = await asyncio.to_thread(st2.scheduler.wait, job,
                                          st2.config["runtime"]["synth_timeout_seconds"])
            audio = res["audio"]
            ttfa_ms = (time.time() - ttfa_start) * 1000.0
            if out_rate != 22050:
                audio = audio_resampler.resample(audio, 22050, out_rate)
            audio_bytes = audio_encoder.encode_pcm(audio, fmt, out_rate)
            st2.stats.record(ttfa_ms=ttfa_ms, gen_ms=res["generation_ms"],
                             rtf=res["rtf"], duration_s=res["duration_s"])
            await sess.send({"type": "response.created", "session_id": sess.id})
            chunk_size = max(1, int(out_rate * 0.1))
            for i in range(0, len(audio_bytes), chunk_size * 2):
                chunk = audio_bytes[i:i + chunk_size * 2]
                if not chunk:
                    continue
                await sess.send({
                    "type": "audio.chunk",
                    "session_id": sess.id,
                    "data": __import__("base64").b64encode(chunk).decode(),
                    "format": fmt,
                    "sample_rate": out_rate,
                    "chunk_index": i // (chunk_size * 2),
                })
            await sess.send({"type": "response.completed", "session_id": sess.id,
                             "duration_s": res["duration_s"],
                             "ttfa_ms": round(ttfa_ms, 1)})
        except ApiException as e:
            await sess.send_error(e.code, e.message, retryable=e.retryable)
        except Exception as e:
            logger.exception("realtime synthesis error: %s", e)
            await sess.send_error(ErrorCodes.SYNTHESIS_FAILED, str(e))

    async def process_events():
        while True:
            event = await sess._events.get()
            etype = event.get("type")
            try:
                if etype == "session.update":
                    sess.apply_config(event.get("session") or {})
                    await sess.send({"type": "session.updated",
                                     "session": sess.cfg.model_dump(), "session_id": sess.id})
                elif etype == "input_text.append":
                    text = event.get("text", "")
                    if not text:
                        await sess.send_error(ErrorCodes.INVALID_REQUEST, "empty text append")
                        continue
                    sess.buffer.append(text)
                elif etype == "input_text.commit":
                    phrases = sess.buffer.flush_all()
                    for phrase in phrases:
                        await run_synthesis(phrase, time.time())
                elif etype == "response.cancel":
                    n = st.scheduler.cancel()
                    sess.buffer.reset()
                    await sess.send({"type": "response.cancelled", "session_id": sess.id,
                                     "cancelled_jobs": n})
                elif etype == "ping":
                    await sess.send({"type": "pong", "session_id": sess.id})
                else:
                    await sess.send_error(ErrorCodes.WEBSOCKET_PROTOCOL_ERROR,
                                          f"Unknown event type '{etype}'.", retryable=False)
            except ApiException as e:
                await sess.send_error(e.code, e.message, retryable=e.retryable)
            except Exception as e:
                logger.exception("realtime event handler failed: %s", e)
                await sess.send_error(ErrorCodes.WEBSOCKET_PROTOCOL_ERROR, str(e))

    async def flush_worker():
        """Flush buffered text to synthesis as soon as phrase rules allow."""
        while True:
            phrases = sess.buffer.pop_ready()
            for phrase in phrases:
                await run_synthesis(phrase, time.time())
            await asyncio.sleep(0.01)

    sess._task = asyncio.create_task(process_events())
    flush_task = asyncio.create_task(flush_worker())

    try:
        await sess.send({"type": "session.created", "session_id": sess.id,
                         "request_id": sess.request_id})
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await sess.send_error(ErrorCodes.WEBSOCKET_PROTOCOL_ERROR,
                                      "Malformed JSON payload.", retryable=False)
                continue
            if not isinstance(payload, dict) or "type" not in payload:
                await sess.send_error(ErrorCodes.WEBSOCKET_PROTOCOL_ERROR,
                                      "Event must be an object with a 'type' field.")
                continue
            await sess._events.put(payload)
    except WebSocketDisconnect:
        logger.info("realtime session %s disconnected", sess.id)
        if st.config["scheduler"].get("cancel_on_disconnect", True):
            st.scheduler.cancel()
        st.stats.record(cancelled=True)
    finally:
        sess._task.cancel()
        flush_task.cancel()
        try:
            await asyncio.gather(sess._task, flush_task, return_exceptions=True)
        except Exception:
            pass
