"""Quality tests: text normalization, pronunciation, voice matrix, formats."""

import asyncio
import io
import wave

import httpx

NORMALIZATION_CORPUS = [
    ("\u20b91,450", "hi", "rupee amount"),
    ("15/08/2026", "en", "date"),
    ("9876543210", "en", "phone number"),
    ("Order #4821", "en", "order id"),
    ("GST 18%", "en", "percentage"),
    ("10:30 AM", "en", "time"),
]

HINGLISH_TEXTS = [
    "Sir \u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964",
    "Payment \u0905\u092d\u0940 \u0924\u0915 receive \u0928\u0939\u0940\u0902 \u0939\u0941\u0906 \u0939\u0948\u0964",
]


async def run_quality(base_url: str) -> dict:
    results = []
    async with httpx.AsyncClient(timeout=120) as client:
        for text, lang, name in NORMALIZATION_CORPUS:
            try:
                r = await client.post(f"{base_url}/v1/audio/speech", json={
                    "model": "magpie-tts-multilingual-357m", "input": text,
                    "voice": "aria", "language": lang, "response_format": "wav"})
                dur = 0.0
                if r.status_code == 200:
                    with wave.open(io.BytesIO(r.content), "rb") as wf:
                        dur = wf.getnframes() / wf.getframerate()
                results.append({"name": f"TN: {name}", "passed": r.status_code == 200 and dur > 0,
                                "detail": f"'{text}' -> {dur:.2f}s"})
            except Exception as e:
                results.append({"name": f"TN: {name}", "passed": False, "detail": str(e)})

        for i, text in enumerate(HINGLISH_TEXTS):
            try:
                r = await client.post(f"{base_url}/v1/audio/speech", json={
                    "model": "magpie-tts-multilingual-357m", "input": text,
                    "voice": "aria", "language": "hi", "response_format": "wav"})
                dur = 0.0
                if r.status_code == 200:
                    with wave.open(io.BytesIO(r.content), "rb") as wf:
                        dur = wf.getnframes() / wf.getframerate()
                results.append({"name": f"Hinglish {i + 1}", "passed": r.status_code == 200 and dur > 0,
                                "detail": f"{dur:.2f}s"})
            except Exception as e:
                results.append({"name": f"Hinglish {i + 1}", "passed": False, "detail": str(e)})

        for voice in ["aria", "jason", "john", "leo", "sofia"]:
            try:
                r = await client.post(f"{base_url}/v1/audio/speech", json={
                    "model": "magpie-tts-multilingual-357m",
                    "input": "Voice matrix comparison for this speaker.",
                    "voice": voice, "language": "en", "response_format": "wav"})
                dur = 0.0
                if r.status_code == 200:
                    with wave.open(io.BytesIO(r.content), "rb") as wf:
                        dur = wf.getnframes() / wf.getframerate()
                results.append({"name": f"Voice {voice}", "passed": r.status_code == 200 and dur > 0,
                                "detail": f"{dur:.2f}s"})
            except Exception as e:
                results.append({"name": f"Voice {voice}", "passed": False, "detail": str(e)})
    passed = sum(1 for r in results if r["passed"])
    return {"total": len(results), "passed": passed, "results": results}
