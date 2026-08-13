"""Admin API: profile switching, self-test, benchmark, logs, reload, config."""

import asyncio
import logging
import time

from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse

from app.api.common import synthesize_request
from app.schemas.benchmark import BenchmarkRequest
from app.schemas.errors import ApiException, ErrorCodes
from app.state import get_state
from app.utils.common import percentiles

logger = logging.getLogger("magpie.api.admin")
router = APIRouter(prefix="/api", tags=["Admin"])

_benchmark_lock = asyncio.Lock()


@router.get("/profiles", summary="List precision profiles with measured VRAM")
async def profiles():
    st = get_state()
    return {"object": "list", "data": st.profiles.list_all(),
            "current": st.model_manager.status()["profile"],
            "state": st.model_manager.status()["state"]}


@router.post("/profiles/switch", summary="Switch precision profile (safe, with rollback)")
async def switch_profile(payload: dict = Body(...), request: Request = None):
    st = get_state()
    profile_id = payload.get("profile") or payload.get("id")
    if not profile_id:
        raise ApiException(ErrorCodes.INVALID_REQUEST, "profile is required.")
    result = await asyncio.to_thread(st.model_manager.switch_profile, profile_id)
    return {"status": "switched", "model": result}


@router.post("/selftest", summary="Run the full model self-test")
async def selftest(request: Request):
    st = get_state()
    mm = st.model_manager
    mm.require_active()
    result = await asyncio.to_thread(mm._selftest)
    return {"status": "passed" if result["passed"] else "failed", "result": result}


@router.get("/logs", summary="Recent server log lines")
async def logs(lines: int = 200, request: Request = None):
    st = get_state()
    log_path = st.config.get("log_file")
    if not log_path:
        return {"lines": []}
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return {"lines": all_lines[-lines:]}
    except Exception:
        return {"lines": []}


@router.post("/reload", summary="Reload config + pronunciation dictionary")
async def reload():
    st = get_state()
    st.profiles.reload()
    from app.text.ipa_dictionary import load_dictionary
    import os
    path = os.path.join(st.config_path.rsplit("/", 1)[0], "pronunciation.yaml")
    if os.path.exists(path):
        st.ipa = load_dictionary(path)
    return {"status": "reloaded"}


@router.post("/benchmark", summary="Run a benchmark",
             description="Measures TTFA percentiles, RTF, VRAM, GPU metrics "
                         "under the requested concurrency.")
async def benchmark(req: BenchmarkRequest):
    st = get_state()
    async with _benchmark_lock:
        mm = st.model_manager
        if req.profile and req.profile != mm.status()["profile"]:
            # Switching for benchmark is heavy; reject rather than surprise.
            raise ApiException(ErrorCodes.INVALID_REQUEST,
                               f"Benchmark profile '{req.profile}' is not the active "
                               f"profile '{mm.status()['profile']}'. Switch first.",
                               details={"active": mm.status()["profile"]})
        mm.require_active()
        texts = req.texts or [
            "Your order has already been dispatched. Please tell me your registered phone number.",
            "\u0928\u092e\u0938\u094d\u0924\u0947 \u0938\u0930, \u092e\u0948\u0902 \u0906\u092a\u0915\u0940 \u0915\u0948\u0938\u0947 \u0938\u0939\u093e\u092f\u0924\u093e \u0915\u0930 \u0938\u0915\u0924\u093e \u0939\u0942\u0901?",
            "Sir \u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964",
        ]

        async def worker() -> dict:
            ttfas, gen_ms, rtfs, durations = [], [], [], []
            failures = 0
            error_codes = set()
            peak_vram = 0.0
            for _ in range(req.iterations):
                try:
                    res = await asyncio.to_thread(
                        synthesize_request,
                        text=texts[0], language=req.language, voice="aria",
                        response_format="pcm", priority=30)
                    ttfas.append(res["ttfa_ms"] or 0)
                    gen_ms.append(res["generation_ms"] or 0)
                    if res["duration_s"]:
                        rtfs.append((res["generation_ms"] or 0) / 1000.0 / res["duration_s"])
                    durations.append(res["duration_s"])
                    peak_vram = max(peak_vram, res["peak_vram_mb"] or 0)
                except ApiException as e:
                    failures += 1
                    error_codes.add(e.code)
            return dict(ttfas=ttfas, gen_ms=gen_ms, rtfs=rtfs,
                        durations=durations, failures=failures,
                        error_codes=sorted(error_codes), peak_vram=peak_vram)

        t0 = time.time()
        tasks = [worker() for _ in range(req.concurrent_users)]
        results = await asyncio.gather(*tasks)
        total_ms = (time.time() - t0) * 1000.0

        ttfas = [x for r in results for x in r["ttfas"]]
        rtfs = [x for r in results for x in r["rtfs"]]
        durations = [x for r in results for x in r["durations"]]
        failures = sum(r["failures"] for r in results)
        error_codes = sorted({c for r in results for c in r["error_codes"]})
        peak_vram = max((r["peak_vram"] for r in results), default=0.0)
        gpu = st.gpu.peak()
        total_audio = sum(durations)
        rps = (req.iterations * req.concurrent_users) / (total_ms / 1000.0) if total_ms > 0 else 0.0

        return {
            "profile": req.profile,
            "language": req.language,
            "concurrent_users": req.concurrent_users,
            "iterations": req.iterations,
            "streaming": req.streaming,
            "ttfa_p50_ms": percentiles(ttfas)["p50"],
            "ttfa_p95_ms": percentiles(ttfas)["p95"],
            "ttfa_p99_ms": percentiles(ttfas)["p99"],
            "rtf": sum(rtfs) / len(rtfs) if rtfs else 0.0,
            "peak_vram_mb": peak_vram,
            "avg_vram_mb": gpu.get("avg_vram_mb", 0.0),
            "gpu_util_pct": gpu.get("avg_util_pct", 0.0),
            "gpu_temp_c": gpu.get("peak_temp_c", 0.0),
            "requests_per_sec": rps,
            "audio_duration_s": total_audio,
            "failures": failures,
            "error_codes": error_codes,
        }
