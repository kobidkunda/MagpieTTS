"""TTS request scheduler with priorities and cancellation.

Priorities (lower = first):
  0  realtime voice-agent streams
  10 normal /v1/audio/speech
  20 GUI tests
  30 benchmarks
"""

import heapq
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.schemas.errors import ApiException, ErrorCodes

logger = logging.getLogger("magpie.scheduler")

PRIORITY_REALTIME = 0
PRIORITY_NORMAL = 10
PRIORITY_GUI = 20
PRIORITY_BENCHMARK = 30


@dataclass(order=True)
class ScheduledJob:
    priority: int
    seq: int
    job_id: str = field(compare=False)
    fn: Callable = field(compare=False)
    cancel_event: threading.Event = field(compare=False)
    meta: dict = field(default_factory=dict, compare=False)
    result: Any = field(default=None, compare=False)
    error: Optional[ApiException] = field(default=None, compare=False)
    done: threading.Event = field(default_factory=threading.Event, compare=False)


class Scheduler:
    def __init__(self, max_queue: int = 32, name: str = "tts"):
        self.max_queue = max_queue
        self.name = name
        self._heap: list[ScheduledJob] = []
        self._seq = 0
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._worker: Optional[threading.Thread] = None
        self._stopping = False
        self._active: Optional[ScheduledJob] = None
        self._cancelled_count = 0
        self._completed_count = 0
        self._started_at = time.time()

    @property
    def queue_depth(self) -> int:
        with self._lock:
            return len(self._heap)

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "queue_depth": len(self._heap),
                "active": self._active is not None,
                "completed": self._completed_count,
                "cancelled": self._cancelled_count,
            }

    def start(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._stopping = False
            self._worker = threading.Thread(target=self._run, daemon=True,
                                            name=f"scheduler-{self.name}")
            self._worker.start()

    def stop(self) -> None:
        with self._cond:
            self._stopping = True
            self._cond.notify_all()
        if self._worker:
            self._worker.join(timeout=5)

    def cancel(self, job_id: str | None = None, cancel_event: Optional[threading.Event] = None) -> int:
        """Cancel a specific job, or all jobs if job_id is None. Returns count cancelled."""
        count = 0
        with self._cond:
            if job_id is None:
                events = [j.cancel_event for j in self._heap]
                if self._active is not None:
                    events.append(self._active.cancel_event)
                for ev in events:
                    if not ev.is_set():
                        ev.set()
                        count += 1
                self._heap = [j for j in self._heap if not j.cancel_event.is_set()]
                heapq.heapify(self._heap)
                self._cancelled_count += len(events)
            else:
                targets = [j for j in self._heap if j.job_id == job_id]
                if self._active is not None and self._active.job_id == job_id:
                    targets.append(self._active)
                for j in targets:
                    if not j.cancel_event.is_set():
                        j.cancel_event.set()
                        count += 1
                self._heap = [j for j in self._heap if not j.cancel_event.is_set()]
                heapq.heapify(self._heap)
                self._cancelled_count += count
            if cancel_event is not None and not cancel_event.is_set():
                cancel_event.set()
            self._cond.notify_all()
        return count

    def submit(self, fn: Callable, priority: int = PRIORITY_NORMAL,
               meta: Optional[dict] = None, timeout_s: float | None = None,
               job_id: str | None = None) -> ScheduledJob:
        with self._cond:
            if len(self._heap) >= self.max_queue:
                raise ApiException(ErrorCodes.QUEUE_FULL,
                                   f"Synthesis queue is full ({self.max_queue} jobs). "
                                   "Retry after current work drains.",
                                   retryable=True,
                                   status=429)
            if self._stopping:
                raise ApiException(ErrorCodes.MODEL_SWITCHING,
                                   "TTS scheduler is stopping; try again shortly.",
                                   retryable=True)
            job = ScheduledJob(
                priority=priority,
                seq=self._seq,
                job_id=job_id or f"job_{uuid.uuid4().hex[:10]}",
                fn=fn,
                cancel_event=threading.Event(),
                meta=meta or {},
            )
            self._seq += 1
            heapq.heappush(self._heap, job)
            self._cond.notify()
        if timeout_s is not None:
            return job  # caller waits themselves
        return job

    def wait(self, job: ScheduledJob, timeout_s: float) -> Any:
        job.done.wait(timeout_s)
        if not job.done.is_set():
            job.cancel_event.set()
            raise ApiException(ErrorCodes.SYNTHESIS_TIMEOUT,
                               f"Synthesis timed out after {timeout_s:.1f}s.",
                               retryable=True, status=504)
        if job.error is not None:
            raise job.error
        return job.result

    def _run(self) -> None:
        while True:
            with self._cond:
                while not self._heap and not self._stopping:
                    self._cond.wait(timeout=0.5)
                if self._stopping and not self._heap:
                    break
                job = heapq.heappop(self._heap)
                self._active = job
            try:
                if job.cancel_event.is_set():
                    raise ApiException(ErrorCodes.SYNTHESIS_CANCELLED,
                                       "Synthesis cancelled.", status=400)
                job.result = job.fn(job.cancel_event)
            except ApiException as e:
                job.error = e
            except Exception as e:
                if job.cancel_event.is_set():
                    job.error = ApiException(ErrorCodes.SYNTHESIS_CANCELLED,
                                             "Synthesis cancelled.", status=400)
                else:
                    logger.exception("job %s failed: %s", job.job_id, e)
                    job.error = ApiException(ErrorCodes.SYNTHESIS_FAILED,
                                             f"Synthesis failed: {e}", retryable=False)
            finally:
                with self._cond:
                    self._active = None
                    if job.cancel_event.is_set():
                        job.error = ApiException(ErrorCodes.SYNTHESIS_CANCELLED,
                                                 "Synthesis cancelled.", status=400)
                    if job.error is None:
                        self._completed_count += 1
                    job.done.set()
                    self._cond.notify_all()
