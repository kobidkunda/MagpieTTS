"""Phrase streaming engine: incremental text -> phrase flushes.

Implements the plan's Phrase Streaming Engine:
Gemini tokens -> Text Buffer -> Phrase Boundary Detector -> synthesis.
"""

import threading
import time
from typing import Callable, Optional

FLUSH_PUNCTUATION = {".", "?", "!", ",", ";", ":", "\u0964", "\n"}
SENTENCE_FINAL = {".", "?", "!", "\u0964", "\n"}


class PhraseBuffer:
    def __init__(
        self,
        min_words: int = 3,
        preferred_words: int = 8,
        max_words: int = 18,
        soft_timeout_ms: int = 120,
        hard_timeout_ms: int = 250,
        flush_punctuation: Optional[set[str]] = None,
    ):
        self.min_words = min_words
        self.preferred_words = preferred_words
        self.max_words = max_words
        self.soft_timeout_ms = soft_timeout_ms
        self.hard_timeout_ms = hard_timeout_ms
        self.flush_punctuation = flush_punctuation or set(FLUSH_PUNCTUATION)
        self._buffer: list[str] = []
        self._tokens: list[str] = []
        self._last_append_ms = 0.0
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._buffer = []
            self._tokens = []
            self._last_append_ms = 0.0

    def append(self, text: str) -> None:
        with self._lock:
            self._tokens.append(text)
            self._buffer.append(text)
            self._last_append_ms = time.monotonic() * 1000.0

    @property
    def pending(self) -> bool:
        with self._lock:
            return bool(self._tokens)

    def _word_count(self, s: str) -> int:
        return len([w for w in s.split() if w.strip()])

    def pop_ready(self) -> list[str]:
        """Return phrases that are ready to synthesize now (blocking-safe).

        When a flush boundary is hit, only the text up to that boundary is
        emitted; the remainder stays buffered for the next phrase. This keeps
        sentence-final boundaries (., ?, !, danda, newline) intact instead of
        merging several sentences into one oversized phrase.
        """
        out: list[str] = []
        with self._lock:
            while self._tokens:
                text = self._join(self._tokens)
                if not text:
                    break
                cut = self._flush_position(text)
                if cut <= 0:
                    break
                phrase = text[:cut].strip()
                remainder = text[cut:].strip()
                self._tokens = [remainder] if remainder else []
                self._buffer = []
                if phrase:
                    out.append(phrase)
        return out

    @staticmethod
    def _join(tokens: list[str]) -> str:
        """Concatenate raw text increments.

        Tokens may be whole words, word pieces, or arbitrary char slices
        (Gemini-style token streaming). Joining with spaces would corrupt
        text when a token splits a word, so plain concatenation is used.
        """
        return "".join(t for t in tokens if t is not None).strip()

    def _flush_position(self, text: str) -> int:
        """Character index to flush up to (exclusive), or 0 if nothing is ready."""
        words = self._word_count(text)
        now = time.monotonic() * 1000.0
        idle = now - self._last_append_ms if self._last_append_ms else 0.0

        # Sentence-final punctuation flushes up to (and including) the first boundary.
        if words >= 1:
            for i, ch in enumerate(text):
                if ch in SENTENCE_FINAL:
                    return i + 1

        # Safety caps flushes the whole pending text.
        if self.max_words > 0 and words >= self.max_words:
            return len(text)
        if self.hard_timeout_ms > 0 and idle >= self.hard_timeout_ms:
            return len(text)
        if words >= self.preferred_words and self.soft_timeout_ms > 0 and idle >= self.soft_timeout_ms:
            return len(text)
        return 0

    def flush_all(self) -> list[str]:
        with self._lock:
            out: list[str] = []
            while self._tokens:
                text = self._join(self._tokens)
                if not text:
                    break
                cut = self._flush_position(text)
                if cut <= 0:
                    cut = len(text)
                phrase = text[:cut].strip()
                remainder = text[cut:].strip()
                self._tokens = [remainder] if remainder else []
                self._buffer = []
                if phrase:
                    out.append(phrase)
            return out


def stream_text_into_buffer(text: str, buffer: PhraseBuffer, token_size: int = 6) -> None:
    """Simulate incremental token delivery (used by tests/GUI simulation)."""
    i = 0
    while i < len(text):
        step = token_size
        buffer.append(text[i:i + step])
        i += step
