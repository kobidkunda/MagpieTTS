# API Reference

Base URL: `http://<host>:8092`

Interactive docs are available at `/docs` (Swagger), `/redoc` (ReDoc), and the
machine-readable spec at `/openapi.json`.

## Conventions

- All requests and responses are JSON (except audio endpoints, which return raw
  audio bytes).
- All errors share a single shape:

```json
{
  "error": {
    "code": "INVALID_VOICE",
    "message": "Voice 'abc' is not available.",
    "type": "validation_error",
    "request_id": "req_a84df92",
    "retryable": false,
    "details": { "allowed": ["aria", "jason", "john", "leo", "sofia"] }
  }
}
```

- HTTP status codes: `400` malformed · `404` unknown · `409` conflicting model
  op · `422` unsupported settings · `429` overloaded · `500` unexpected ·
  `503` unavailable · `504` timeout.

## Audio formats & sample rates

- Formats: `pcm`, `wav`, `mp3`, `opus`, `flac`, `aac`
- Sample rates: `8000`, `16000`, `22050`, `24000`, `48000`
- Native output is 22.05 kHz mono 16-bit PCM.

---

## OpenAI-compatible endpoints

### `POST /v1/audio/speech`

Synthesize speech from text. OpenAI SDK compatible.

**Request**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | `magpie-tts-multilingual-357m` | Model identifier |
| `input` | string | *(required)* | Text to synthesize (UTF-8) |
| `voice` | string | `aria` | `aria`, `jason`, `john`, `leo`, `sofia` |
| `language` | string | `en` | `ar`, `zh`, `en`, `fr`, `de`, `hi`, `it`, `ja`, `ko`, `pt`, `es`, `vi` |
| `response_format` | string | `wav` | `pcm`, `wav`, `mp3`, `opus`, `flac`, `aac` |
| `speed` | float | `1.0` | `0.25`–`4.0` |
| `stream` | bool | `false` | Stream audio via chunked transfer |
| `stream_format` | string | *(response_format)* | Per-chunk format |
| `sample_rate` | int | `22050` | Output sample rate |
| `mode` | string | `auto` | `auto`, `standard`, `long` |
| `cfg_enabled` | bool | *(config)* | Classifier-free guidance override |
| `cfg_scale` | float | *(config)* | CFG scale |
| `text_normalization` | bool | `false` | Apply text normalization |

**Example**

```bash
curl -X POST http://host:8092/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"Your order has been dispatched.","voice":"aria","language":"en","response_format":"mp3"}' \
  --output speech.mp3
```

### `GET /v1/models`

```json
{
  "object": "list",
  "data": [
    { "id": "magpie-tts-multilingual-357m", "object": "model", "owned_by": "nvidia" }
  ]
}
```

### `GET /v1/audio/voices` · `GET /v1/audio/list_voices`

Voice discovery (both OpenAI and NVIDIA path styles).

### `POST /v1/audio/cancel`

Cancel queued synthesis (barge-in). Returns `200`.

---

## Native endpoints

### `POST /api/tts/generate`

Advanced synthesis with full Magpie controls.

**Request**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `text` | string | *(required)* | Text to synthesize |
| `language` | string | `en` | Language code |
| `speaker` | string | `Aria` | `Aria`, `Jason`, `John`, `Leo`, `Sofia` |
| `profile` | string | `fp16-realtime` | Precision profile |
| `text_normalization` | bool | `false` | Apply text normalization |
| `cfg.enabled` | bool | `true` | Classifier-free guidance |
| `cfg.scale` | float | `2.5` | CFG scale |
| `audio.format` | string | `wav` | Output format |
| `audio.sample_rate` | int | `22050` | Output sample rate |
| `stream` | bool | `false` | Stream response |
| `priority` | int | `10` | Scheduler priority `0`–`30` |
| `mode` | string | `auto` | `auto`, `standard`, `long` |

```bash
curl -X POST http://host:8092/api/tts/generate \
  -H "Content-Type: application/json" \
  -d '{"text":"नमस्ते","language":"hi","speaker":"Aria","cfg":{"enabled":true,"scale":2.5},"audio":{"format":"wav","sample_rate":22050}}' \
  --output hi.wav
```

### `GET /api/languages`

List of supported language codes and names.

### `GET/POST/DELETE /api/tts/pronunciation`

Manage the IPA pronunciation dictionary (e.g. for brand names, acronyms, GST,
UPI, SKU).

### `GET /api/profiles`

Precision profiles with measured VRAM and status.

### `POST /api/profiles/switch`

Switch the active precision profile. Drains active generation, unloads, loads,
warms up, self-tests, and rolls back on failure. Returns `503` while switching.

### `POST /api/selftest`

Run the 24-check self test (health, model, voices, English/Hindi/Hinglish
generation, formats, streaming, cancellation, profile switching, concurrency,
GPU metrics, OpenAI compatibility).

### `POST /api/benchmark`

Run a benchmark (profile, concurrency, language, iterations, streaming) and
return TTFA, RTF, VRAM, and GPU utilization metrics.

### `GET /api/system`

Full system status: server version, model id/precision, GPU metrics, and runtime
counters.

---

## Health & observability

| Path | Purpose |
|------|---------|
| `GET /health` | Web server liveness (200 even before model loads) |
| `GET /ready` | Model + codec loaded, warmup passed (503 until ready) |
| `GET /metrics` | Prometheus-compatible text format |
