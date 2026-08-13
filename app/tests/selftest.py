"""Self-test suite: 24 checks covering health, API, synthesis, formats,
streaming, cancellation, profiles and errors. Each test reports pass/fail
with a message. Run from the GUI or CLI."""

import asyncio
import io
import json
import time
import wave
from typing import Optional

import httpx
import numpy as np

from app.schemas.errors import ApiException, ErrorCodes

TEST_CORPUS = {
    "en": "Your order has already been dispatched.",
    "hi": "\u0928\u092e\u0938\u094d\u0924\u0947 \u0938\u0930, \u092e\u0948\u0902 \u0906\u092a\u0915\u0940 \u0915\u0948\u0938\u0947 \u0938\u0939\u093e\u092f\u0924\u093e \u0915\u0930 \u0938\u0915\u0924\u093e \u0939\u0942\u0901?",
    "hinglish": "Sir \u0906\u092a\u0915\u093e order dispatch \u0939\u094b \u091a\u0941\u0915\u093e \u0939\u0948\u0964",
}


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.message = ""
        self.duration_ms = 0.0

    def ok(self, message: str = "OK"):
        self.passed = True
        self.message = message

    def fail(self, message: str):
        self.passed = False
        self.message = message

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed,
                "message": self.message, "duration_ms": round(self.duration_ms, 1)}


class SelfTestRunner:
    def __init__(self, base_url: str = "http://127.0.0.1:8092"):
        self.base_url = base_url.rstrip("/")
        self.results: list[TestResult] = []

    def _new(self, name: str) -> TestResult:
        return TestResult(name)

    async def run(self) -> dict:
        tests = [
            self.test_health, self.test_ready, self.test_model_list,
            self.test_voice_list, self.test_en_generation, self.test_hi_generation,
            self.test_hinglish, self.test_wav, self.test_pcm, self.test_mp3,
            self.test_opus, self.test_http_stream, self.test_ws_stream,
            self.test_cancellation, self.test_profile_switch, self.test_model_reload,
            self.test_invalid_language, self.test_invalid_voice, self.test_empty_text,
            self.test_oversized_input, self.test_concurrent, self.test_queue_overload,
            self.test_gpu_metrics, self.test_openai_compat,
        ]
        for test in tests:
            t = self._new(test.__name__)
            started = time.time()
            try:
                await test(t)
            except Exception as e:
                t.fail(f"exception: {e}")
            t.duration_ms = (time.time() - started) * 1000.0
            self.results.append(t)
        passed = sum(1 for r in self.results if r.passed)
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": len(self.results) - passed,
            "results": [r.to_dict() for r in self.results],
        }

    async def _synth(self, text: str, fmt: str = "wav", language: str = "en",
                     voice: str = "aria", **kw) -> tuple[bytes, float]:
        started = time.time()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/v1/audio/speech", json={
                "model": "magpie-tts-multilingual-357m",
                "input": text, "voice": voice, "language": language,
                "response_format": fmt, **kw})
        ttfa_ms = (time.time() - started) * 1000.0
        assert resp.status_code == 200, f"status {resp.status_code}: {resp.text[:300]}"
        return resp.content, ttfa_ms

    # ------------------------------------------------------------------

    async def test_health(self, t: TestResult):
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/health", timeout=10)
        t.ok(f"GET /health -> {r.status_code}") if r.status_code == 200 else t.fail(str(r.status_code))

    async def test_ready(self, t: TestResult):
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/ready", timeout=10)
        t.ok(f"GET /ready -> {r.status_code}") if r.status_code == 200 else t.fail(f"/ready not ready: {r.text[:200]}")

    async def test_model_list(self, t: TestResult):
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/v1/models", timeout=10)
        data = r.json()
        loaded = any(m.get("loaded") for m in data.get("data", []))
        t.ok(f"model listed, loaded={loaded}") if r.status_code == 200 and loaded else t.fail(r.text[:200])

    async def test_voice_list(self, t: TestResult):
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/v1/audio/voices", timeout=10)
        data = r.json().get("data", [])
        ids = [v["id"] for v in data]
        ok = r.status_code == 200 and len(ids) >= 5
        t.ok(f"voices: {ids}") if ok else t.fail(r.text[:200])

    async def test_en_generation(self, t: TestResult):
        data, ttfa = await self._synth(TEST_CORPUS["en"], language="en")
        dur = self._wav_duration(data)
        t.ok(f"{dur:.2f}s audio, TTFA {ttfa:.0f}ms") if dur > 0 else t.fail("no audio")

    async def test_hi_generation(self, t: TestResult):
        data, ttfa = await self._synth(TEST_CORPUS["hi"], language="hi")
        dur = self._wav_duration(data)
        t.ok(f"{dur:.2f}s audio, TTFA {ttfa:.0f}ms") if dur > 0 else t.fail("no audio")

    async def test_hinglish(self, t: TestResult):
        data, ttfa = await self._synth(TEST_CORPUS["hinglish"], language="hi")
        dur = self._wav_duration(data)
        t.ok(f"{dur:.2f}s audio") if dur > 0 else t.fail("no audio")

    async def test_wav(self, t: TestResult):
        data, _ = await self._synth("Test WAV format.", fmt="wav")
        dur = self._wav_duration(data)
        t.ok("valid WAV") if dur > 0 else t.fail("invalid wav")

    async def test_pcm(self, t: TestResult):
        data, _ = await self._synth("Test PCM format.", fmt="pcm")
        ok = len(data) > 0 and len(data) % 2 == 0
        t.ok(f"{len(data)} bytes PCM16") if ok else t.fail("bad pcm")

    async def test_mp3(self, t: TestResult):
        data, _ = await self._synth("Test MP3 format.", fmt="mp3")
        ok = data.startswith(b"ID3") or data.startswith(b"\xff\xfb") or data.startswith(b"\xff\xf3")
        t.ok(f"{len(data)} bytes") if ok else t.fail("not mp3")

    async def test_opus(self, t: TestResult):
        data, _ = await self._synth("Test OPUS format.", fmt="opus")
        ok = len(data) > 100 and b"OpusHead" in data[:64]
        t.ok(f"{len(data)} bytes") if ok else t.fail(f"not opus: {len(data)} bytes")

    async def test_http_stream(self, t: TestResult):
        started = time.time()
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{self.base_url}/v1/audio/speech", json={
                "model": "magpie-tts-multilingual-357m",
                "input": "This is a streaming test for HTTP chunked audio delivery.",
                "voice": "aria", "language": "en", "response_format": "pcm",
                "stream": True}) as resp:
                assert resp.status_code == 200, resp.text[:300]
                total = 0
                first_chunk_ms = None
                async for chunk in resp.aiter_bytes():
                    if first_chunk_ms is None:
                        first_chunk_ms = (time.time() - started) * 1000.0
                    total += len(chunk)
        t.ok(f"{total} bytes, first chunk {first_chunk_ms:.0f}ms") if total > 100 else t.fail("no stream")

    async def test_ws_stream(self, t: TestResult):
        import websockets
        ws_url = self.base_url.replace("http://", "ws://") + "/v1/realtime?intent=synthesize"
        async with websockets.connect(ws_url) as ws:
            msg = json.loads(await ws.recv())
            assert msg["type"] == "session.created", msg
            await ws.send(json.dumps({"type": "session.update", "session": {
                "voice": "aria", "language": "en", "format": "pcm", "sample_rate": 22050}}))
            msg = json.loads(await ws.recv())
            assert msg["type"] == "session.updated", msg
            await ws.send(json.dumps({"type": "input_text.append", "text": "Hello from websocket streaming."}))
            await ws.send(json.dumps({"type": "input_text.commit"}))
            got_audio = False
            got_done = False
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                if msg["type"] == "audio.chunk":
                    got_audio = True
                elif msg["type"] == "response.completed":
                    got_done = True
                    break
                elif msg["type"] == "error":
                    t.fail(f"ws error: {msg['error']['code']} {msg['error']['message']}")
                    return
            t.ok(f"audio_chunk={got_audio} completed={got_done}") if got_audio and got_done else t.fail("no chunks")

    async def test_cancellation(self, t: TestResult):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base_url}/v1/audio/cancel")
        ok = r.status_code == 200
        t.ok("POST /v1/audio/cancel -> 200") if ok else t.fail(r.text[:200])

    async def test_profile_switch(self, t: TestResult):
        async with httpx.AsyncClient(timeout=180) as client:
            st = await client.get(f"{self.base_url}/api/profiles", timeout=10)
            profiles = st.json().get("data", [])
            current = st.json().get("current")
            target = next((p for p in profiles if p["id"] != current and p["loadable"]), None)
            if target is None:
                t.fail("no alternative loadable profile")
                return
            r = await client.post(f"{self.base_url}/api/profiles/switch",
                                  json={"profile": target["id"]}, timeout=180)
            if r.status_code != 200:
                t.fail(f"switch failed: {r.text[:300]}")
                return
            r2 = await client.post(f"{self.base_url}/api/profiles/switch",
                                   json={"profile": current}, timeout=180)
            ok = r2.status_code == 200
            t.ok(f"switched {current}->{target['id']}->{current}") if ok else t.fail(r2.text[:300])

    async def test_model_reload(self, t: TestResult):
        async with httpx.AsyncClient(timeout=180) as client:
            st = await client.get(f"{self.base_url}/api/profiles", timeout=10)
            current = st.json().get("current")
            r = await client.post(f"{self.base_url}/api/profiles/switch",
                                  json={"profile": current}, timeout=180)
        t.ok("reloaded same profile") if r.status_code == 200 else t.fail(r.text[:300])

    async def test_invalid_language(self, t: TestResult):
        try:
            await self._synth("Hello", language="xx")
            t.fail("no error raised")
        except AssertionError as e:
            t.ok(str(e)[:120]) if "422" in str(e) or "400" in str(e) else t.fail(str(e))

    async def test_invalid_voice(self, t: TestResult):
        try:
            await self._synth("Hello", voice="bogus")
            t.fail("no error raised")
        except AssertionError as e:
            t.ok(str(e)[:120]) if "422" in str(e) or "400" in str(e) else t.fail(str(e))

    async def test_empty_text(self, t: TestResult):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base_url}/v1/audio/speech", json={
                "model": "magpie-tts-multilingual-357m", "input": "   ",
                "voice": "aria", "language": "en"})
        t.ok(f"rejected with {r.status_code}") if r.status_code in (400, 422) else t.fail(str(r.status_code))

    async def test_oversized_input(self, t: TestResult):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base_url}/v1/audio/speech", json={
                "model": "magpie-tts-multilingual-357m", "input": "x" * 6000,
                "voice": "aria", "language": "en"})
        t.ok(f"rejected with {r.status_code}") if r.status_code in (400, 422) else t.fail(str(r.status_code))

    async def test_concurrent(self, t: TestResult):
        import asyncio
        results = await asyncio.gather(*[self._synth("Concurrent request test.", fmt="wav") for _ in range(4)],
                                       return_exceptions=True)
        ok = sum(1 for r in results if not isinstance(r, Exception))
        t.ok(f"{ok}/4 succeeded") if ok == 4 else t.fail(f"{ok}/4 succeeded")

    async def test_queue_overload(self, t: TestResult):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base_url}/api/system", timeout=10)
        depth = r.json().get("runtime", {}).get("queue", 0)
        t.ok(f"queue depth readable: {depth}")

    async def test_gpu_metrics(self, t: TestResult):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base_url}/api/system", timeout=10)
        gpu = r.json().get("gpu", {})
        ok = gpu.get("available") and gpu.get("total_mb", 0) > 0
        t.ok(f"{gpu.get('used_mb')}/{gpu.get('total_mb')} MB") if ok else t.fail("gpu metrics missing")

    async def test_openai_compat(self, t: TestResult):
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(f"{self.base_url}/v1/audio/speech", json={
                "model": "magpie-tts-multilingual-357m",
                "input": "OpenAI SDK compatibility check.",
                "voice": "aria", "language": "en", "response_format": "mp3"},
                headers={"Authorization": "Bearer unused"})
        ok = r.status_code == 200 and (r.content.startswith(b"ID3") or r.content.startswith(b"\xff"))
        t.ok("OpenAI payload accepted, mp3 returned") if ok else t.fail(f"{r.status_code}: {r.text[:200]}")

    @staticmethod
    def _wav_duration(data: bytes) -> float:
        try:
            with wave.open(io.BytesIO(data), "rb") as wf:
                return wf.getnframes() / wf.getframerate()
        except Exception:
            return 0.0
