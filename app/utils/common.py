"""Small utilities: request ids, stats, validation."""

import logging
import threading
import time
import uuid
from typing import Iterable


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:10]}"


def new_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:10]}"


class MetricsRing:
    """Thread-safe ring of recent latency samples with percentiles."""

    def __init__(self, maxlen: int = 500):
        self._samples: list[float] = []
        self._maxlen = maxlen
        self._lock = threading.Lock()

    def add(self, ms: float) -> None:
        with self._lock:
            self._samples.append(ms)
            if len(self._samples) > self._maxlen:
                self._samples = self._samples[-self._maxlen:]

    def _snapshot(self) -> list[float]:
        with self._lock:
            return list(self._samples)

    def percentile(self, p: float) -> float:
        s = sorted(self._snapshot())
        if not s:
            return 0.0
        idx = min(len(s) - 1, int(round(p / 100.0 * (len(s) - 1))))
        return s[idx]

    def stats(self) -> dict:
        s = self._snapshot()
        if not s:
            return {"count": 0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "last": 0.0}
        ss = sorted(s)
        def pct(p):
            return ss[min(len(ss) - 1, int(round(p / 100.0 * (len(ss) - 1))))]
        return {"count": len(s), "p50": pct(50), "p95": pct(95), "p99": pct(99), "last": s[-1]}


class RequestStats:
    def __init__(self):
        self.ttfa = MetricsRing()
        self.gen_ms = MetricsRing()
        self.rtf = MetricsRing()
        self.requests = 0
        self.errors = 0
        self.cancelled = 0
        self.audio_seconds = 0.0
        self._lock = threading.Lock()

    def record(self, ttfa_ms: float | None = None, gen_ms: float | None = None,
               rtf: float | None = None, duration_s: float | None = None,
               error: bool = False, cancelled: bool = False) -> None:
        with self._lock:
            self.requests += 1
            if error:
                self.errors += 1
            if cancelled:
                self.cancelled += 1
        if ttfa_ms is not None:
            self.ttfa.add(ttfa_ms)
        if gen_ms is not None:
            self.gen_ms.add(gen_ms)
        if rtf is not None:
            self.rtf.add(rtf)
        if duration_s:
            with self._lock:
                self.audio_seconds += duration_s

    def summary(self) -> dict:
        with self._lock:
            base = {
                "requests": self.requests,
                "errors": self.errors,
                "cancelled": self.cancelled,
                "audio_seconds": round(self.audio_seconds, 1),
                "ttfa": self.ttfa.stats(),
                "generation_ms": self.gen_ms.stats(),
                "rtf": self.rtf.stats(),
            }
        return base


def percentiles(values: Iterable[float]) -> dict:
    vals = sorted(values)
    n = len(vals)
    if n == 0:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    def pct(p):
        return vals[min(n - 1, int(round(p / 100.0 * (n - 1))))]
    return {"p50": pct(50), "p95": pct(95), "p99": pct(99)}
