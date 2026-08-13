"""Language registry for the loaded Magpie model."""

from app.schemas.errors import ApiException, ErrorCodes

SUPPORTED_LANGUAGES = ["ar", "zh", "en", "fr", "de", "hi", "it", "ja", "ko", "pt", "es", "vi"]

LANGUAGE_NAMES = {
    "ar": "Arabic",
    "zh": "Chinese",
    "en": "English",
    "fr": "French",
    "de": "German",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "es": "Spanish",
    "vi": "Vietnamese",
}


def validate_language(lang: str) -> str:
    lang = (lang or "").lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise ApiException(ErrorCodes.UNSUPPORTED_LANGUAGE,
                           f"Language '{lang}' is not supported by the loaded model.",
                           details={"allowed": SUPPORTED_LANGUAGES})
    return lang
