"""IPA pronunciation dictionary.

Magpie supports IPA customization: surround the IPA string in '|' and add a
space between each IPA character. E.g.:
    "Hello world from | ˈ n ɛ m o ʊ | Text to Speech."
"""

import threading
from typing import Optional

from app.schemas.errors import ApiException, ErrorCodes


class PronunciationEntry:
    def __init__(self, word: str, language: str, ipa: str, enabled: bool = True):
        self.word = word
        self.language = language
        self.ipa = ipa
        self.enabled = enabled

    def to_dict(self) -> dict:
        return {"word": self.word, "language": self.language, "ipa": self.ipa, "enabled": self.enabled}


class IPADictionary:
    def __init__(self, entries: Optional[list[PronunciationEntry]] = None):
        self._entries: list[PronunciationEntry] = entries or []
        self._lock = threading.Lock()

    @classmethod
    def from_dicts(cls, data: list[dict]) -> "IPADictionary":
        entries = []
        for d in data:
            entries.append(PronunciationEntry(
                word=d["word"], language=d.get("language", "en"),
                ipa=d.get("ipa", ""), enabled=d.get("enabled", True)))
        return cls(entries)

    def list(self) -> list[dict]:
        with self._lock:
            return [e.to_dict() for e in self._entries]

    def upsert(self, word: str, language: str, ipa: str, enabled: bool = True) -> dict:
        with self._lock:
            for e in self._entries:
                if e.word.lower() == word.lower() and e.language == language:
                    e.ipa = ipa
                    e.enabled = enabled
                    return e.to_dict()
            entry = PronunciationEntry(word, language, ipa, enabled)
            self._entries.append(entry)
            return entry.to_dict()

    def delete(self, word: str, language: str) -> bool:
        with self._lock:
            for i, e in enumerate(self._entries):
                if e.word.lower() == word.lower() and e.language == language:
                    del self._entries[i]
                    return True
        return False

    def apply(self, text: str, language: str) -> str:
        """Replace enabled words with their | IPA | form for the given language."""
        with self._lock:
            entries = [e for e in self._entries if e.enabled and (e.language == language or e.language == "en")]
        for e in sorted(entries, key=lambda x: -len(x.word)):
            if f"| {e.ipa} |" in text:
                continue
            ipa_form = f"| {e.ipa} |"
            text = text.replace(e.word, ipa_form)
        return text


def load_dictionary(path: str) -> IPADictionary:
    import yaml
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return IPADictionary.from_dicts(data.get("entries", []))
