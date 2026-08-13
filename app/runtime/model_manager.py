"""Model Manager: single persistent Magpie instance with safe profile switching.

One loaded model at a time. Switching follows:
drain -> reject new (503) -> unload -> gc -> clear CUDA cache -> load ->
warmup -> self-test -> active. Automatic rollback on failure.
"""

import gc
import logging
import threading
import time
from typing import Optional

from app.engines.magpie_nemo import MagpieNemoEngine
from app.runtime import health
from app.runtime.gpu_monitor import GPUMonitor
from app.runtime.profile_manager import ProfileManager
from app.runtime.warmup import warmup as run_warmup
from app.schemas.errors import ApiException, ErrorCodes

logger = logging.getLogger("magpie.model_manager")

STATE_UNLOADED = "unloaded"
STATE_LOADING = "loading"
STATE_SWITCHING = "switching"
STATE_ACTIVE = "active"
STATE_FAILED = "failed"

SELFTEST_TEXTS = [
    ("en", "Hello, this is a test."),
    ("hi", "\u0928\u092e\u0938\u094d\u0924\u0947, \u092f\u0939 \u090f\u0915 \u092a\u0930\u0940\u0915\u094d\u0937\u0923 \u0939\u0948\u0964"),
    ("hi", "\u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u0917\u092f\u093e \u0939\u0948\u0964"),
]


class ModelManager:
    def __init__(self, config: dict, profiles: ProfileManager, gpu_monitor: GPUMonitor,
                 scheduler):
        self.config = config
        self.profiles = profiles
        self.gpu = gpu_monitor
        self.scheduler = scheduler
        self.engine = MagpieNemoEngine(
            model_id=config["model"]["id"], codec_id=config["model"]["codec_repo"])
        self.state = STATE_UNLOADED
        self.current_profile: Optional[str] = None
        self.state_error: Optional[str] = None
        self.vram_after_load_mb: float = 0.0
        self._lock = threading.Lock()
        self._synthesis_lock = threading.Lock()
        self._ready_event = threading.Event()
        self._last_selftest: Optional[dict] = None
        self._load_count = 0

    # ---------------------------------------------------------------- status

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self.state,
                "model_id": self.config["model"]["id"],
                "revision": self.config["model"]["revision"],
                "profile": self.current_profile,
                "precision": self.engine.precision if self.engine.loaded else None,
                "device": self.config["runtime"]["device"],
                "vram_after_load_mb": self.vram_after_load_mb,
                "load_count": self._load_count,
                "last_error": self.state_error,
                "last_selftest": self._last_selftest,
                "ready": self.state == STATE_ACTIVE,
            }

    def require_active(self) -> None:
        with self._lock:
            state = self.state
            err = self.state_error
        if state == STATE_ACTIVE:
            return
        if state in (STATE_SWITCHING,):
            raise ApiException(ErrorCodes.MODEL_SWITCHING,
                               "TTS model is currently switching profiles.",
                               retryable=True)
        if state in (STATE_LOADING, STATE_UNLOADED):
            raise ApiException(ErrorCodes.MODEL_LOADING,
                               "TTS model is not loaded yet.", retryable=True)
        if state == STATE_FAILED:
            raise ApiException(ErrorCodes.MODEL_LOAD_FAILED,
                               f"Model load failed: {err}", retryable=True)

    # ------------------------------------------------------------- synthesis

    def synthesize(self, text: str, language: str, speaker_index: int,
                   profile_id: Optional[str] = None,
                   apply_tn: bool = True, use_cfg: bool = True, cfg_scale: float = 2.5,
                   cancel_event=None) -> dict:
        """Synthesize now (caller holds scheduler job); returns dict with audio + metrics."""
        self.require_active()
        profile_id = profile_id or self.current_profile
        try:
            with self._synthesis_lock:
                t0 = time.time()
                vram_before = self.gpu.latest().get("used_mb", 0.0)
                audio = self.engine.synthesize(
                    text, language, speaker_index,
                    apply_tn=apply_tn, use_cfg=use_cfg, cfg_scale=cfg_scale,
                    cancel_event=cancel_event)
                gen_ms = (time.time() - t0) * 1000.0
                vram_after = self.gpu.latest().get("used_mb", 0.0)
                peak_vram = max(vram_before, vram_after, self.vram_after_load_mb)
                duration_s = len(audio) / self.engine.SAMPLE_RATE
                return {
                    "audio": audio,
                    "sample_rate": self.engine.SAMPLE_RATE,
                    "duration_s": duration_s,
                    "generation_ms": gen_ms,
                    "rtf": gen_ms / 1000.0 / duration_s if duration_s > 0 else 0.0,
                    "peak_vram_mb": peak_vram,
                    "profile": profile_id,
                }
        except ApiException:
            raise
        except Exception as e:
            msg = str(e)
            if "out of memory" in msg.lower() or "CUDA_OOM" in msg:
                logger.error("CUDA OOM during synthesis: %s", msg)
                raise ApiException(ErrorCodes.CUDA_OOM,
                                   f"GPU out of memory: {msg}", retryable=True) from e
            if "CUDA" in msg or "cuda" in msg:
                raise ApiException(ErrorCodes.CUDA_ERROR,
                                   f"CUDA error: {msg}", retryable=True) from e
            raise ApiException(ErrorCodes.SYNTHESIS_FAILED,
                               f"Synthesis failed: {msg}", retryable=False) from e

    # ------------------------------------------------------------- switching

    def load_default(self) -> None:
        precision = self.config["runtime"].get("precision", "fp16")
        profile_id = {"fp16": "fp16-realtime", "fp32": "fp32-reference",
                      "bf16": "bf16", "int8": "int8", "int4": "int4"}.get(precision)
        if not profile_id or not self.profiles.get_opt(profile_id):
            profile_id = "fp16-realtime"
        self.switch_profile(profile_id)

    def switch_profile(self, profile_id: str) -> dict:
        """Safe profile switch with drain + rollback. Returns final status dict."""
        target = self.profiles.get(profile_id)  # raises if unknown/unloadable
        with self._lock:
            if self.state == STATE_SWITCHING:
                raise ApiException(ErrorCodes.MODEL_SWITCHING,
                                   "Another profile switch is already in progress.",
                                   retryable=True, status=409)
            previous = self.current_profile
            self.state = STATE_SWITCHING
            self.state_error = None

        logger.info("switching profile -> %s (was %s)", profile_id, previous)
        try:
            self._drain(previous)
            self._unload()
            t0 = time.time()
            self.engine.load(self._resolve_model_path(), target.precision,
                             self.config["runtime"]["device"])
            load_ms = (time.time() - t0) * 1000.0
            warmup_results = run_warmup(self.engine)
            gc.collect()
            import torch
            torch.cuda.empty_cache()
            vram = self.gpu.latest().get("used_mb", 0.0)
            self.vram_after_load_mb = vram
            self.profiles.set_measurement(profile_id, vram, load_ms)
            selftest = self._selftest()
            with self._lock:
                self.current_profile = profile_id
                self.state = STATE_ACTIVE
                self.state_error = None
                self._last_selftest = selftest
                self._load_count += 1
            health.set_model(True, profile=profile_id, model_id=self.config["model"]["id"])
            self._ready_event.set()
            logger.info("profile %s ACTIVE (load %.0f ms, VRAM %.0f MB, self-test ok)",
                        profile_id, load_ms, vram)
            return self.status()
        except Exception as e:
            logger.exception("profile %s load failed: %s", profile_id, e)
            self.state_error = str(e)
            health.set_model(False, error=str(e))
            if previous and previous != profile_id:
                logger.warning("rolling back to previous profile %s", previous)
                try:
                    self._rollback(previous)
                except Exception as e2:
                    logger.exception("rollback failed: %s", e2)
                    with self._lock:
                        self.state = STATE_FAILED
                    raise ApiException(ErrorCodes.MODEL_LOAD_FAILED,
                                       f"Profile '{profile_id}' load failed ({e}) and "
                                       f"rollback to '{previous}' also failed ({e2}).",
                                       retryable=True) from e
            else:
                with self._lock:
                    self.state = STATE_FAILED
            raise ApiException(ErrorCodes.MODEL_LOAD_FAILED,
                               f"Profile '{profile_id}' load failed: {e}",
                               retryable=True) from e

    def _rollback(self, profile_id: str) -> None:
        target = self.profiles.get(profile_id)
        self._unload()
        self.engine.load(self._resolve_model_path(), target.precision,
                         self.config["runtime"]["device"])
        run_warmup(self.engine)
        gc.collect()
        import torch
        torch.cuda.empty_cache()
        vram = self.gpu.latest().get("used_mb", 0.0)
        self.vram_after_load_mb = vram
        with self._lock:
            self.current_profile = profile_id
            self.state = STATE_ACTIVE
            self.state_error = None
            self._load_count += 1
        health.set_model(True, profile=profile_id, model_id=self.config["model"]["id"])

    def _drain(self, previous: Optional[str]) -> None:
        deadline = time.time() + 30.0
        while time.time() < deadline:
            stats = self.scheduler.stats
            if not stats["active"] and stats["queue_depth"] == 0:
                return
            time.sleep(0.05)
        logger.warning("drain timed out; proceeding with switch anyway")

    def _unload(self) -> None:
        try:
            self.engine.unload()
        except Exception as e:
            logger.warning("unload error: %s", e)
        gc.collect()
        import torch
        torch.cuda.empty_cache()

    def _resolve_model_path(self) -> str:
        model_dir = self.config.get("model_dir")
        if model_dir:
            import os
            nemo_path = os.path.join(model_dir, self.config["model"]["nemo_file"])
            if os.path.exists(nemo_path):
                return nemo_path
            if os.path.isdir(model_dir) and os.listdir(model_dir):
                return model_dir
        return self.config["model"]["hf_repo"]

    def _selftest(self) -> dict:
        results = []
        for lang, text in SELFTEST_TEXTS:
            t0 = time.time()
            audio = self.engine.synthesize(text, language=lang, speaker_index=0,
                                           apply_tn=True)
            ms = (time.time() - t0) * 1000.0
            import numpy as np
            if audio is None or len(audio) == 0:
                raise RuntimeError(f"self-test produced no audio ({lang})")
            if np.any(np.isnan(audio)) or np.any(np.isinf(audio)):
                raise RuntimeError(f"self-test produced NaN/inf ({lang})")
            results.append({"language": lang, "duration_s": round(len(audio) / self.engine.SAMPLE_RATE, 3),
                            "ms": round(ms, 1)})
        return {"passed": True, "checks": results,
                "rtf": round(sum(r["ms"] for r in results) / 1000.0 / sum(r["duration_s"] for r in results), 4)}
