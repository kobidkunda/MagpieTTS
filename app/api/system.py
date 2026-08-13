"""System endpoints: health, ready, system info, metrics."""

import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.runtime import health
from app.state import get_state

router = APIRouter(tags=["System"])


@router.get("/health", summary="Liveness",
            description="200 while the web server is alive, even if the model is not loaded.")
async def healthz():
    return {"status": "ok", "alive": True}


@router.get("/ready", summary="Readiness",
            description="503 until the model is loaded, codec ready, warmup passed.")
async def readyz():
    st = get_state()
    h = health.status()
    if h["ready"]:
        return {"status": "ready", "model": h["model_id"], "profile": h["profile"]}
    return JSONResponse(status_code=503, content={
        "status": "not_ready",
        "model_loaded": h["model_loaded"],
        "last_error": h["last_error"],
    })


@router.get("/api/system", summary="Full system status")
async def system(request: Request):
    st = get_state()
    mm = st.model_manager
    h = health.status()
    gpu = st.gpu.latest()
    sched = st.scheduler.stats
    return {
        "status": "ready" if h["ready"] else "loading",
        "server": {"version": st.config["server"]["version"], "name": st.config["server"]["name"]},
        "model": mm.status(),
        "gpu": gpu,
        "runtime": {
            "active_sessions": sched["active"],
            "queue": sched["queue_depth"],
            "completed": sched["completed"],
            "cancelled": sched["cancelled"],
        },
        "stats": st.stats.summary(),
    }


@router.get("/metrics", summary="Prometheus-style text metrics")
async def metrics():
    st = get_state()
    gpu = st.gpu.latest()
    sched = st.scheduler.stats
    stats = st.stats.summary()
    lines = [
        "# HELP magpie_requests_total Total synthesis requests.",
        "# TYPE magpie_requests_total counter",
        f"magpie_requests_total {stats['requests']}",
        "# HELP magpie_errors_total Total synthesis errors.",
        "# TYPE magpie_errors_total counter",
        f"magpie_errors_total {stats['errors']}",
        "# HELP magpie_cancelled_total Total cancelled generations.",
        "# TYPE magpie_cancelled_total counter",
        f"magpie_cancelled_total {stats['cancelled']}",
        "# HELP magpie_ttfa_ms TTFA in milliseconds.",
        "# TYPE magpie_ttfa_ms gauge",
        f"magpie_ttfa_ms{{quantile=\"p50\"}} {stats['ttfa']['p50']}",
        f"magpie_ttfa_ms{{quantile=\"p95\"}} {stats['ttfa']['p95']}",
        f"magpie_ttfa_ms{{quantile=\"p99\"}} {stats['ttfa']['p99']}",
        "# HELP magpie_rtf Real-time factor.",
        "# TYPE magpie_rtf gauge",
        f"magpie_rtf{{quantile=\"p50\"}} {stats['rtf']['p50']}",
        "# HELP magpie_gpu_used_mb GPU memory used.",
        "# TYPE magpie_gpu_used_mb gauge",
        f"magpie_gpu_used_mb {gpu['used_mb']}",
        "# HELP magpie_gpu_util_pct GPU utilization.",
        "# TYPE magpie_gpu_util_pct gauge",
        f"magpie_gpu_util_pct {gpu['utilization']}",
        "# HELP magpie_queue_depth Current scheduler queue depth.",
        "# TYPE magpie_queue_depth gauge",
        f"magpie_queue_depth {sched['queue_depth']}",
        "# HELP magpie_ready Server ready state.",
        "# TYPE magpie_ready gauge",
        f"magpie_ready {1 if health.is_ready() else 0}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
