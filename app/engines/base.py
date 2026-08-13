"""Engine abstraction: a TTS engine loads a model and synthesizes float32 audio."""

from abc import ABC, abstractmethod

import numpy as np


class TTSEngine(ABC):
    SAMPLE_RATE: int = 22050

    @abstractmethod
    def load(self, model_path: str, precision: str, device: str) -> None:
        ...

    @abstractmethod
    def synthesize(self, text: str, language: str, speaker_index: int,
                   apply_tn: bool = True, use_cfg: bool = True, cfg_scale: float = 2.5,
                   cancel_event=None) -> np.ndarray:
        """Return float32 mono audio in [-1, 1] at SAMPLE_RATE Hz."""
        ...

    @abstractmethod
    def unload(self) -> None:
        ...

    @property
    @abstractmethod
    def loaded(self) -> bool:
        ...
