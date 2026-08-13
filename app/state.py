"""Application-wide singletons: config, managers, monitors."""

import logging
import os
import threading
from typing import Optional

import yaml

from app.runtime.gpu_monitor import GPUMonitor
from app.runtime.model_manager import ModelManager
from app.runtime.profile_manager import ProfileManager
from app.runtime.scheduler import Scheduler
from app.text.ipa_dictionary import IPADictionary, load_dictionary

logger = logging.getLogger("magpie.state")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "configs")


class AppState:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(CONFIG_DIR, "server.yaml")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f) or {}
        voices_path = os.path.join(CONFIG_DIR, "voices.yaml")
        if os.path.exists(voices_path):
            with open(voices_path, "r", encoding="utf-8") as f:
                self.config["voices"] = (yaml.safe_load(f) or {}).get("voices", [])
        self.model_dir = os.path.join(BASE_DIR, "models")
        self.config.setdefault("model_dir", self.model_dir)

        profiles_path = os.path.join(CONFIG_DIR, "profiles.yaml")
        self.profiles = ProfileManager(profiles_path)
        self.gpu = GPUMonitor(device=self.config["runtime"]["device"], interval_s=1.0)
        self.scheduler = Scheduler(max_queue=self.config["scheduler"]["max_queue"])
        self.model_manager = ModelManager(self.config, self.profiles, self.gpu, self.scheduler)

        dict_path = os.path.join(CONFIG_DIR, "pronunciation.yaml")
        self.ipa = load_dictionary(dict_path) if os.path.exists(dict_path) else IPADictionary()

        self._started = False
        self._start_lock = threading.Lock()

    def start(self) -> None:
        with self._start_lock:
            if self._started:
                return
            self._started = True
        self.gpu.start()
        self.scheduler.start()

    def shutdown(self) -> None:
        self.scheduler.stop()
        self.gpu.stop()
        try:
            self.model_manager.engine.unload()
        except Exception:
            pass


state: Optional[AppState] = None


def get_state() -> AppState:
    global state
    if state is None:
        state = AppState()
    return state
