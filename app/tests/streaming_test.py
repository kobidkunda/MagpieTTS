"""Realtime streaming tests: incremental text, phrase flush, cancellation."""

import asyncio
import json

import httpx
import websockets


async def run_streaming(base_url: str) -> dict:
    results = []
    ws_url = base_url.replace("http://", "ws://") + "/v1/realtime?intent=synthesize"

    try:
        async with websockets.connect(ws_url) as ws:
            assert json.loads(await ws.recv())["type"] == "session.created"
            await ws.send(json.dumps({"type": "session.update", "session": {
                "voice": "aria", "language": "hi", "format": "pcm", "sample_rate": 22050}}))
            assert json.loads(await ws.recv())["type"] == "session.updated"
            for chunk in ["\u091c\u0940 ", "\u0938\u0930, ", "\u0906\u092a\u0915\u093e ", "order ",
                          "dispatch ", "\u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964"]:
                await ws.send(json.dumps({"type": "input_text.append", "text": chunk}))
                await asyncio.sleep(0.05)
            await ws.send(json.dumps({"type": "input_text.commit"}))
            audio_chunks = 0
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                if msg["type"] == "audio.chunk":
                    audio_chunks += 1
                elif msg["type"] == "response.completed":
                    break
                elif msg["type"] == "error":
                    raise AssertionError(msg["error"])
            results.append({"name": "incremental hi streaming", "passed": audio_chunks > 0,
                            "detail": f"{audio_chunks} chunks"})
    except Exception as e:
        results.append({"name": "incremental hi streaming", "passed": False, "detail": str(e)})

    try:
        async with websockets.connect(ws_url) as ws:
            json.loads(await ws.recv())
            await ws.send(json.dumps({"type": "input_text.append", "text": "long " * 60}))
            await ws.send(json.dumps({"type": "response.cancel"}))
            msg = json.loads(await ws.recv())
            ok = msg["type"] in ("response.cancelled", "error")
            results.append({"name": "ws cancellation", "passed": ok, "detail": msg["type"]})
    except Exception as e:
        results.append({"name": "ws cancellation", "passed": False, "detail": str(e)})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{base_url}/v1/audio/cancel")
        results.append({"name": "http cancel", "passed": r.status_code == 200,
                        "detail": str(r.status_code)})
    except Exception as e:
        results.append({"name": "http cancel", "passed": False, "detail": str(e)})

    passed = sum(1 for r in results if r["passed"])
    return {"total": len(results), "passed": passed, "results": results}
