"""Text normalization policy.

The Magpie model includes built-in text normalization (numbers, abbreviations,
special characters) for all 12 languages; we pass apply_TN through and only
validate/prepare the text here.
"""

from app.schemas.errors import ApiException, ErrorCodes

MAX_INPUT_CHARS = 5000


def normalize_text(text: str, apply_tn: bool = True) -> str:
    if text is None or not text.strip():
        raise ApiException(ErrorCodes.EMPTY_TEXT, "Text is empty.", retryable=False)
    stripped = text.strip()
    if len(stripped) > MAX_INPUT_CHARS:
        raise ApiException(ErrorCodes.TEXT_TOO_LONG,
                           f"Text exceeds the {MAX_INPUT_CHARS} character limit.",
                           details={"max_chars": MAX_INPUT_CHARS, "received": len(stripped)})
    # Squash runs of whitespace; keep punctuation.
    return " ".join(stripped.split())


def split_for_long_mode(text: str, max_chars: int = 900) -> list[str]:
    """Split long text into segments for the long-form sliding-window mode."""
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    segments: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                segments.append(current)
            current = word
    if current:
        segments.append(current)
    return segments
