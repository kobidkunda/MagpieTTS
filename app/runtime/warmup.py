"""Model warmup: short synthesis runs after load to validate the runtime."""

import logging
import time

from app.runtime.health import set_model

logger = logging.getLogger("magpie.warmup")

WARMUP_TEXTS = [
    ("en", "Hello, this is a test."),
    ("hi", "\u0928\u092e\u0938\u094d\u0924\u0947, \u092f\u0939 \u090f\u0915 \u092a\u0930\u0940\u0915\u094d\u0937\u0923 \u0939\u0948\u0964"),
    ("hi", "\u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u0917\u092f\u093e \u0939\u0948\u0964"),
]


def warmup(engine, cancel_event=None) -> dict:
    """Run the model self-test sentences. Raises on first failure."""
    results = []
    for lang, text in WARMUP_TEXTS:
        t0 = time.time()
        audio = engine.synthesize(text, language=lang, speaker_index=0,
                                  apply_tn=True, cancel_event=cancel_event)
        elapsed_ms = (time.time() - t0) * 1000.0
        import numpy as np
        if audio is None or len(audio) == 0:
            raise RuntimeError(f"warmup produced no audio for '{lang}'")
        if np.any(np.isnan(audio)) or np.any(np.isinf(audio)):
            raise RuntimeError(f"warmup produced NaN/inf audio for '{lang}'")
        results.append({"language": lang, "samples": int(len(audio)), "ms": round(elapsed_ms, 1)})
        logger.info("warmup %s ok: %d samples in %.1f ms", lang, len(audio), elapsed_ms)
    return results
