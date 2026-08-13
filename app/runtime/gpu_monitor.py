"""Live GPU metrics via NVML (nvidia-ml-py) or torch fallback."""

import os
import threading
import time
from typing import Optional

import numpy as np

_nvml = None
_nvml_handle = None
_torch = None


def init(device: str = "cuda:0") -> None:
    global _nvml, _nvml_handle, _torch
    try:
        import nvidia.ml.bindings as _  # noqa: F401
    except Exception:
        pass
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        _nvml = pynvml
        _nvml_handle = handle
    except Exception:
        _nvml = None
        _nvml_handle = None
    try:
        import torch
        _torch = torch
    except Exception:
        _torch = None


def snapshot(device: str = "cuda:0") -> dict:
    """Live snapshot: used_mb, free_mb, total_mb, util_pct, temp_c, power_w."""
    out = {"device": device, "used_mb": 0, "free_mb": 0, "total_mb": 0,
           "utilization": 0.0, "temperature": 0.0, "power_w": 0.0, "available": False}
    try:
        if _nvml is not None and _nvml_handle is not None:
            mem = _nvml.nvmlDeviceGetMemoryInfo(_nvml_handle)
            util = _nvml.nvmlDeviceGetUtilizationRates(_nvml_handle)
            temp = _nvml.nvmlDeviceGetTemperature(_nvml_handle, _nvml.NVML_TEMPERATURE_GPU)
            try:
                power = _nvml.nvmlDeviceGetPowerUsage(_nvml_handle) / 1000.0
            except Exception:
                power = 0.0
            out.update({
                "used_mb": round(mem.used / 1048576, 1),
                "free_mb": round(mem.free / 1048576, 1),
                "total_mb": round(mem.total / 1048576, 1),
                "utilization": float(util.gpu),
                "temperature": float(temp),
                "power_w": round(power, 1),
                "available": True,
            })
            return out
        if _torch is not None and _torch.cuda.is_available():
            device_idx = int(device.split(":")[-1]) if ":" in device else 0
            props = _torch.cuda.get_device_properties(device_idx)
            mem = _torch.cuda.memory_stats(device_idx)
            used = _torch.cuda.memory_allocated(device_idx)
            total = props.total_memory
            out.update({
                "used_mb": round(used / 1048576, 1),
                "free_mb": round((total - used) / 1048576, 1),
                "total_mb": round(total / 1048576, 1),
                "temperature": float(getattr(props, "temperature", 0.0) or 0.0),
                "available": True,
            })
            return out
    except Exception:
        pass
    return out


class GPUMonitor:
    """Samples GPU metrics at a fixed interval; exposes min/max/avg over a window."""

    def __init__(self, device: str = "cuda:0", interval_s: float = 1.0):
        self.device = device
        self.interval_s = interval_s
        self._latest: dict = {}
        self._history: list[dict] = []
        self._window = 300
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="gpu-monitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            snap = snapshot(self.device)
            with self._lock:
                self._latest = snap
                self._history.append(snap)
                if len(self._history) > self._window:
                    self._history = self._history[-self._window:]

    def latest(self) -> dict:
        with self._lock:
            return dict(self._latest or snapshot(self.device))

    def peak(self, window: Optional[int] = None) -> dict:
        with self._lock:
            hist = self._history[-window:] if window and window > 0 else self._history
            if not hist:
                return self.latest()
            return {
                "peak_vram_mb": max(h["used_mb"] for h in hist),
                "avg_vram_mb": float(np.mean([h["used_mb"] for h in hist])),
                "peak_util_pct": max(h["utilization"] for h in hist),
                "avg_util_pct": float(np.mean([h["utilization"] for h in hist])),
                "peak_temp_c": max(h["temperature"] for h in hist),
            }
