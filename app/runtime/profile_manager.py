"""Model precision profile manager.

Profiles are loaded from configs/profiles.yaml. Only validated profiles are
loadable; int8/int4 remain "missing" until a validated runtime exists.
Never relabel one precision as another.
"""

import threading
from typing import Optional

import yaml

from app.schemas.errors import ApiException, ErrorCodes


class Profile:
    def __init__(self, data: dict):
        self.id = data["id"]
        self.name = data.get("name", self.id)
        self.precision = data.get("precision")
        self.description = data.get("description", "")
        self.status = data.get("status", "ready")
        self.measured_vram_mb: Optional[float] = None
        self.last_load_ms: Optional[float] = None

    @property
    def loadable(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "precision": self.precision,
            "description": self.description,
            "status": self.status,
            "loadable": self.loadable,
            "measured_vram_mb": self.measured_vram_mb,
            "last_load_ms": self.last_load_ms,
        }


class ProfileManager:
    def __init__(self, path: str):
        self._path = path
        self._profiles: dict[str, Profile] = {}
        self._presets: dict = {}
        self._lock = threading.Lock()
        self.reload()

    def reload(self) -> None:
        with open(self._path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        with self._lock:
            self._profiles = {}
            for p in data.get("profiles", []):
                prof = Profile(p)
                self._profiles[prof.id] = prof
            self._presets = data.get("presets", {})

    def get(self, profile_id: str) -> Profile:
        with self._lock:
            prof = self._profiles.get(profile_id)
        if prof is None:
            raise ApiException(ErrorCodes.INVALID_REQUEST,
                               f"Unknown profile '{profile_id}'.",
                               details={"allowed": self.list_ids()})
        if not prof.loadable:
            raise ApiException(ErrorCodes.MODEL_LOAD_FAILED,
                               f"Profile '{profile_id}' is not available "
                               f"({prof.status}): {prof.description}.",
                               retryable=False)
        return prof

    def get_opt(self, profile_id: str) -> Optional[Profile]:
        with self._lock:
            return self._profiles.get(profile_id)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._profiles.keys())

    def list_all(self) -> list[dict]:
        with self._lock:
            return [p.to_dict() for p in self._profiles.values()]

    def set_measurement(self, profile_id: str, vram_mb: float, load_ms: float) -> None:
        with self._lock:
            prof = self._profiles.get(profile_id)
            if prof:
                prof.measured_vram_mb = vram_mb
                prof.last_load_ms = load_ms

    def preset(self, name: str) -> Optional[dict]:
        with self._lock:
            return self._presets.get(name)
