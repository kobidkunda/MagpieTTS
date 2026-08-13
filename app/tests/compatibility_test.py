"""OpenAI SDK compatibility test: verifies the OpenAI client can talk to us."""

import io
import wave

import httpx


async def run_compatibility(base_url: str) -> dict:
    results = []
    base = base_url.rstrip("/")

    try:
        from openai import OpenAI
        client = OpenAI(base_url=f"{base}/v1", api_key="unused", timeout=120)
        resp = client.audio.speech.create(
            model="magpie-tts-multilingual-357m",
            voice="aria",
            input="OpenAI SDK compatibility check.")
        data = resp.content
        with wave.open(io.BytesIO(data), "rb") as wf:
            dur = wf.getnframes() / wf.getframerate()
        results.append({"name": "openai sdk speech", "passed": dur > 0,
                        "detail": f"{dur:.2f}s"})
    except Exception as e:
        results.append({"name": "openai sdk speech", "passed": False, "detail": str(e)})

    try:
        from openai import OpenAI
        client = OpenAI(base_url=f"{base}/v1", api_key="unused", timeout=30)
        models = client.models.list()
        ids = [m.id for m in models.data]
        results.append({"name": "openai sdk models", "passed": len(ids) > 0,
                        "detail": ",".join(ids)})
    except Exception as e:
        results.append({"name": "openai sdk models", "passed": False, "detail": str(e)})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{base}/v1/audio/voices",
                                 headers={"Authorization": "Bearer unused"})
        results.append({"name": "auth header ignored", "passed": r.status_code == 200,
                        "detail": str(r.status_code)})
    except Exception as e:
        results.append({"name": "auth header ignored", "passed": False, "detail": str(e)})

    passed = sum(1 for r in results if r["passed"])
    return {"total": len(results), "passed": passed, "results": results}
