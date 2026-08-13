"""Server readiness/health state."""

import threading

_state = {
    "http_alive": False,
    "model_loaded": False,
    "codec_loaded": False,
    "warmup_passed": False,
    "ready": False,
    "last_error": None,
    "profile": None,
    "model_id": None,
}
_lock = threading.Lock()


def set_http_alive(alive: bool = True) -> None:
    with _lock:
        _state["http_alive"] = alive


def set_model(loaded: bool, profile: str | None = None, model_id: str | None = None,
              error: str | None = None) -> None:
    with _lock:
        _state["model_loaded"] = loaded
        _state["codec_loaded"] = loaded
        _state["warmup_passed"] = loaded
        _state["ready"] = loaded
        _state["profile"] = profile
        _state["model_id"] = model_id
        _state["last_error"] = error


def is_ready() -> bool:
    with _lock:
        return _state["ready"]


def status() -> dict:
    with _lock:
        return dict(_state)
