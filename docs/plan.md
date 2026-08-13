# Product Design — Standalone Magpie 357M Realtime TTS API Server

Yes: **keep this as a completely separate application** from Nemotron ASR and from your existing VoxCPM server.

The new project should be a self-contained **Magpie TTS Server** that can later be selected inside your Voice Translate application simply by changing the TTS provider/base URL. **No changes to VoxCPM or the Voice Translate app are part of this project.**

Magpie v2607 is currently a 364M-parameter multilingual TTS model supporting 12 languages including Hindi and English, with five speaker identities. The official checkpoint is a `.nemo` file of about 1.47 GB, outputs 22.05-kHz mono PCM speech, includes multilingual text normalization, and supports custom IPA pronunciation handling. ([Hugging Face][1])

---

## 1. Final architecture

I recommend one standalone application:

```text
magpie-tts-server/
                 │
                 ├── FastAPI API Server
                 │      │
                 │      ├── OpenAI-compatible API
                 │      ├── Native Magpie API
                 │      ├── HTTP audio streaming
                 │      ├── WebSocket realtime streaming
                 │      ├── Swagger/OpenAPI
                 │      └── AsyncAPI WebSocket docs
                 │
                 ├── Magpie Runtime
                 │      │
                 │      ├── Model Manager
                 │      ├── Precision/Profile Manager
                 │      ├── NanoCodec
                 │      ├── Text Normalizer
                 │      ├── G2P / IPA
                 │      ├── Scheduler
                 │      └── Audio Encoder/Resampler
                 │
                 ├── Testing GUI
                 │      │
                 │      ├── TTS Playground
                 │      ├── Streaming Tester
                 │      ├── Model Manager
                 │      ├── Quantization/Precision Manager
                 │      ├── Benchmark Lab
                 │      ├── Compatibility Tester
                 │      ├── API Explorer
                 │      ├── GPU Monitor
                 │      └── Logs / Diagnostics
                 │
                 └── 0.0.0.0:8092
```

Everything lives behind:

```text
http://<GPU-SERVER-IP>:8092
```

Binding:

```text
0.0.0.0:8092
```

**Not localhost-only.**

No application authentication.

---

# 2. Core design principle

There should be **one model process**.

Do not run:

```text
uvicorn --workers 4
```

because you risk loading Magpie four times.

Instead:

```text
Uvicorn/FastAPI
workers = 1

        │
        ▼

ONE Magpie ModelManager

        │
        ▼

ONE loaded TTS model
```

HTTP clients, GUI clients and WebSocket clients share the same persistent model.

The model loads once at server startup and remains resident.

---

# 3. Recommended project structure

```text
magpie-tts-server/
│
├── app/
│   ├── main.py
│   │
│   ├── api/
│   │   ├── openai.py
│   │   ├── native.py
│   │   ├── realtime.py
│   │   ├── models.py
│   │   ├── voices.py
│   │   ├── system.py
│   │   └── admin.py
│   │
│   ├── schemas/
│   │   ├── speech.py
│   │   ├── realtime.py
│   │   ├── errors.py
│   │   ├── models.py
│   │   └── benchmark.py
│   │
│   ├── engines/
│   │   ├── base.py
│   │   └── magpie_nemo.py
│   │
│   ├── runtime/
│   │   ├── model_manager.py
│   │   ├── profile_manager.py
│   │   ├── scheduler.py
│   │   ├── gpu_monitor.py
│   │   ├── warmup.py
│   │   └── health.py
│   │
│   ├── audio/
│   │   ├── encoder.py
│   │   ├── resampler.py
│   │   ├── chunker.py
│   │   ├── pcm.py
│   │   └── formats.py
│   │
│   ├── text/
│   │   ├── normalizer.py
│   │   ├── phrase_buffer.py
│   │   ├── language.py
│   │   └── ipa_dictionary.py
│   │
│   ├── tests/
│   │   ├── selftest.py
│   │   ├── quality_test.py
│   │   ├── streaming_test.py
│   │   └── compatibility_test.py
│   │
│   └── utils/
│
├── web/
│   ├── React/Vite GUI
│   └── dist/
│
├── configs/
│   ├── server.yaml
│   ├── profiles.yaml
│   ├── voices.yaml
│   └── pronunciation.yaml
│
├── models/
│
├── data/
│   ├── benchmark/
│   ├── test_history/
│   └── logs/
│
├── scripts/
│   ├── install.sh
│   ├── update.sh
│   ├── download-model.sh
│   ├── test.sh
│   └── benchmark.sh
│
├── docker/
│
├── tests/
│
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

# 4. Technology stack

### Backend

```text
Python 3.12+
FastAPI
Uvicorn
Pydantic
PyTorch
NVIDIA NeMo Speech
MagpieTTS
NanoCodec
PyAV / FFmpeg
NumPy
NVML GPU monitoring
WebSocket
```

### GUI

```text
React
TypeScript
Vite
Tailwind
shadcn/ui
WaveSurfer.js
WebSocket client
```

Build React once and have FastAPI serve the static bundle.

Therefore production requires only:

```text
:8092
```

rather than separate frontend/backend ports.

---

# 5. Main API surface

I would support **three interfaces simultaneously**.

| Interface              | Purpose                               |
| ---------------------- | ------------------------------------- |
| OpenAI-compatible REST | Existing/future applications          |
| Native Magpie REST     | Advanced controls                     |
| WebSocket realtime     | Voice agents / Gemini token streaming |

---

# 6. OpenAI-compatible API

Canonical endpoint:

```text
POST /v1/audio/speech
```

OpenAI currently uses this endpoint for text-to-speech and accepts fields including `input`, `model`, `voice`, `response_format`, `speed`, `instructions` and `stream_format`. ([OpenAI Platform][2])

Our implementation should accept:

```json
{
  "model": "magpie-tts-multilingual-357m",
  "input": "आपका order dispatch हो गया है।",
  "voice": "aria",
  "language": "hi",
  "response_format": "pcm",
  "speed": 1.0
}
```

Response:

```text
audio/pcm
```

or:

```text
audio/wav
audio/mpeg
audio/ogg
audio/flac
audio/aac
```

depending on format.

OpenAI currently supports `mp3`, `opus`, `aac`, `flac`, `wav`, and `pcm`, so I would mirror that set wherever our local transcoder supports it. ([OpenAI Platform][2])

---

# 7. OpenAI SDK compatibility

Later your application should be able to do conceptually:

```python
client = OpenAI(
    base_url="http://gpu-server:8092/v1",
    api_key="unused"
)
```

and then:

```python
client.audio.speech.create(
    model="magpie-tts-multilingual-357m",
    voice="aria",
    input="Hello"
)
```

The server will accept an `Authorization` header if a client sends one but **will not validate it**.

Therefore:

```text
Auth required: NO
```

while clients that insist on setting an API key can simply use:

```text
api_key="unused"
```

---

# 8. Models API

Provide:

```text
GET /v1/models
```

Example:

```json
{
  "object": "list",
  "data": [
    {
      "id": "magpie-tts-multilingual-357m",
      "object": "model",
      "owned_by": "nvidia",
      "loaded": true,
      "profile": "fp16-realtime",
      "device": "cuda:0"
    }
  ]
}
```

---

# 9. Voices API

Provide both:

```text
GET /v1/audio/voices
```

and NVIDIA-style:

```text
GET /v1/audio/list_voices
```

NVIDIA's current TTS HTTP API uses `/v1/audio/list_voices`, so keeping this alias also improves compatibility with NVIDIA-style clients. ([NVIDIA Docs][3])

Magpie v2607 currently exposes five speaker identities:

```text
Aria
Jason
John
Leo
Sofia
```

across its supported languages. ([Hugging Face][4])

---

# 10. Supported languages

The GUI should dynamically show only languages supported by the loaded model.

Current v2607:

```text
Arabic
Chinese
English
French
German
Hindi
Italian
Japanese
Korean
Portuguese
Spanish
Vietnamese
```

([Hugging Face][1])

API language IDs:

```text
ar
zh
en
fr
de
hi
it
ja
ko
pt
es
vi
```

Never allow the GUI to silently submit unsupported languages.

---

# 11. Realtime WebSocket API

Use:

```text
ws://SERVER:8092/v1/realtime?intent=synthesize
```

This mirrors NVIDIA's current realtime TTS connection style. NVIDIA's current realtime API uses the same `/v1/realtime?intent=synthesize` pattern for interactive synthesis. ([NVIDIA Docs][5])

### Connection lifecycle

```text
CONNECT
  ↓
session.created
  ↓
session.update
  ↓
input_text.append
  ↓
input_text.append
  ↓
input_text.commit
  ↓
audio chunks
  ↓
response.completed
```

---

# 12. Realtime client events

### Configure

```json
{
  "type": "session.update",
  "session": {
    "voice": "aria",
    "language": "hi",
    "format": "pcm",
    "sample_rate": 22050,
    "speed": 1.0
  }
}
```

### Stream Gemini text

```json
{
  "type": "input_text.append",
  "text": "आपका "
}
```

then:

```json
{
  "type": "input_text.append",
  "text": "order number "
}
```

then:

```json
{
  "type": "input_text.append",
  "text": "4827 है।"
}
```

Commit:

```json
{
  "type": "input_text.commit"
}
```

Cancel:

```json
{
  "type": "response.cancel"
}
```

Critical for barge-in.

---

# 13. Important streaming design

The open Magpie `do_tts()` interface is currently documented around complete transcript synthesis, while NVIDIA's NIM layer separately exposes realtime text streaming. ([Hugging Face][4])

Therefore **do not fake a claim that the raw open model itself accepts arbitrary LLM tokens one-by-one natively.**

Our local server should implement a:

## Phrase Streaming Engine

```text
Gemini tokens
     ↓
Text Buffer
     ↓
Phrase Boundary Detector
     ↓
Magpie synthesis
     ↓
PCM chunk
     ↓
caller
```

Example:

```text
Gemini:

"जी "
"सर, "
"आपका "
"order "
"dispatch "
"हो चुका है।"

        ↓

buffer

        ↓

"जी सर,"
        ↓
synthesize immediately

then

"आपका order dispatch हो चुका है।"
        ↓
synthesize
```

This gives low perceived TTFA without waiting for Gemini to complete an entire response.

---

# 14. Phrase-buffer strategy

Configurable from GUI.

Initial preset:

```text
Minimum words:       3
Preferred words:     6–12
Maximum words:       18
Soft timeout:        120 ms
Hard timeout:        250 ms

Flush immediately on:
.
?
!
,
;
:
Hindi danda: ।
```

These are **benchmark starting values**, not hard-coded model facts.

The GUI must allow tuning them.

---

# 15. Barge-in

This is mandatory.

If caller interrupts:

```text
LiveKit detects speech
        ↓
Voice app sends cancel
        ↓
POST /v1/audio/cancel
or
WS response.cancel
        ↓
TTS scheduler cancels queued phrases
        ↓
stop sending audio
```

Cancellation target:

```text
<100 ms internal cancellation
```

as an engineering target.

Do not wait for the sentence to finish synthesizing.

---

# 16. Native advanced endpoint

Add:

```text
POST /api/tts/generate
```

This is not intended to be OpenAI-compatible.

It exposes full Magpie controls:

```json
{
  "text": "नमस्ते",
  "language": "hi",
  "speaker": "Aria",

  "profile": "fp16-realtime",

  "text_normalization": true,

  "cfg": {
    "enabled": false,
    "scale": 2.5
  },

  "audio": {
    "format": "wav",
    "sample_rate": 22050
  },

  "stream": false
}
```

Advanced controls belong here.

Keep `/v1/audio/speech` clean.

---

# 17. Audio formats

Magpie's native published output is **22.05-kHz mono 16-bit PCM**. ([Hugging Face][4])

Internally always generate:

```text
22,050 Hz
mono
PCM
```

Then optionally resample/encode.

Support:

```text
pcm
wav
mp3
opus
flac
aac
```

Custom option:

```text
sample_rate:
8000
16000
22050
24000
48000
```

For voice applications:

```text
PCM16
16 kHz
```

will probably be the most practical downstream format.

---

# 18. Model/profile manager

This is one of the most important components.

Do **not** let GUI directly manipulate PyTorch objects.

Have:

```text
ModelProfileManager
```

with profiles such as:

```text
magpie-v2607-fp32
magpie-v2607-fp16
magpie-v2607-bf16
custom-int8
custom-int4
```

But:

### Initial supported profiles

```text
FP32
FP16
BF16 — only if runtime validation passes
```

The official Magpie repository currently publishes the `.nemo` checkpoint but does not document official NVIDIA INT8 or INT4 model artifacts there. ([Hugging Face][6])

Therefore INT8/INT4 should appear as:

```text
Experimental / unavailable
```

until a validated conversion/runtime is installed.

**Never simply relabel FP16 as "INT8".**

---

# 19. GUI quantization/profile page

Page:

```text
/models
```

Example UI:

```text
MAGPIE MODEL

Version:
v2607

Current:
● FP16 Realtime

Profiles:

┌─────────────────┬─────────┬────────────┬─────────┐
│ Profile         │ Status  │ VRAM       │ Load    │
├─────────────────┼─────────┼────────────┼─────────┤
│ FP32 Reference  │ Ready   │ measured   │ [Load]  │
│ FP16 Realtime   │ Active  │ measured   │ Active  │
│ BF16            │ Ready   │ measured   │ [Load]  │
│ INT8            │ Missing │ —          │ Setup   │
│ INT4            │ Missing │ —          │ Setup   │
└─────────────────┴─────────┴────────────┴─────────┘
```

Never show guessed VRAM.

Show **measured VRAM**.

---

# 20. Safe model switching

Because minimum VRAM is a priority, don't simultaneously hold two models.

Switch:

```text
User chooses FP16
        ↓
Drain active generation
        ↓
Reject new requests temporarily
        ↓
Unload current model
        ↓
GC
        ↓
clear CUDA cache
        ↓
load selected profile
        ↓
warmup
        ↓
automatic synthesis test
        ↓
profile ACTIVE
```

During change:

```http
503 Service Unavailable
```

with:

```json
{
  "error": {
    "code": "MODEL_SWITCHING",
    "message": "TTS model is currently switching profiles.",
    "retryable": true
  }
}
```

---

# 21. Automatic rollback

If profile load fails:

```text
FP16 → INT8
         ↓
load failed
         ↓
self-test failed
         ↓
reload previous FP16
```

GUI displays:

```text
INT8 FAILED
Reason:
unsupported operator / runtime incompatibility
```

Never leave server in an unknown state.

---

# 22. Model self-test

Every model switch automatically runs:

```text
English:
"Hello, this is a test."

Hindi:
"नमस्ते, यह एक परीक्षण है।"

Hinglish:
"आपका order dispatch हो गया है।"
```

Check:

```text
audio produced
duration > 0
no NaN
sample rate valid
no CUDA error
VRAM measured
RTF measured
TTFA measured
```

Only then mark:

```text
READY
```

---

# 23. Testing GUI

Homepage:

```text
http://SERVER:8092/
```

The GUI must be capable of testing **every useful server feature without curl or Python**.

I would create eight screens.

### Dashboard

Shows:

```text
Server       READY
Model        Magpie v2607
Profile      FP16
Device       CUDA:0
GPU memory   live
GPU util     live
Temperature  live
Sessions     2
Queue        0

Last TTFA    142 ms
P50 TTFA     157 ms
P95 TTFA     244 ms
```

### TTS Playground

Controls:

```text
Text
Language
Voice
Speed
Format
Sample rate
Text normalization
Advanced CFG
Profile
```

Actions:

```text
Generate
Play
Stop
Download
Compare
Repeat
```

Results:

```text
TTFA
generation time
audio duration
RTF
peak VRAM
GPU utilization
```

### Realtime Streaming Lab

This is essential.

Provide:

```text
Text input
Simulate Gemini streaming
Token rate slider
Chunking settings
Start
Pause
Cancel
```

Show realtime timeline:

```text
0 ms      WS request
93 ms     first phrase flushed
181 ms    synthesis started
247 ms    first PCM received
...
```

Also play audio as it arrives.

### Voice Matrix

Generate identical text through:

```text
Aria
Jason
John
Leo
Sofia
```

one click.

Compare audio side-by-side.

### Model / Quantization Manager

Switch profiles and measure VRAM/latency.

### API Tester

Graphical API explorer for:

```text
/v1/audio/speech
/v1/models
/v1/audio/voices
/api/tts/generate
```

### WebSocket Tester

Shows every message:

```text
→ session.update
→ input_text.append
← response.created
← audio.chunk
← response.completed
```

### Diagnostics

One button:

```text
RUN FULL SELF TEST
```

---

# 24. “100% testing from GUI”

The GUI self-test should execute:

| Test                 | GUI |
| -------------------- | --- |
| Health               | ✅   |
| Ready state          | ✅   |
| Model list           | ✅   |
| Voice list           | ✅   |
| English generation   | ✅   |
| Hindi generation     | ✅   |
| Hinglish             | ✅   |
| WAV                  | ✅   |
| PCM                  | ✅   |
| MP3                  | ✅   |
| OPUS                 | ✅   |
| HTTP streaming       | ✅   |
| WebSocket streaming  | ✅   |
| Cancellation         | ✅   |
| Profile switching    | ✅   |
| Model reload         | ✅   |
| Invalid language     | ✅   |
| Invalid voice        | ✅   |
| Empty text           | ✅   |
| Oversized input      | ✅   |
| Concurrent requests  | ✅   |
| Queue overload       | ✅   |
| GPU metrics          | ✅   |
| OpenAI compatibility | ✅   |

At completion:

```text
24 / 24 PASSED
```

or:

```text
22 / 24 PASSED

FAILED:
- OPUS streaming
- Hindi FP16 benchmark
```

---

# 25. Benchmark Lab

GUI page:

```text
/benchmark
```

Allow:

```text
Profile:
FP32 / FP16 / BF16 / custom

Concurrent users:
1 / 2 / 4 / 8

Language:
English / Hindi / Hinglish

Iterations:
1–100

Streaming:
on/off
```

Output:

```text
TTFA P50
TTFA P95
TTFA P99

RTF

peak VRAM
average VRAM

GPU %
GPU temperature

requests/sec

failures
```

This is how we decide the best precision.

Not by assumptions.

---

# 26. OpenAI compatibility tester

One GUI panel should specifically send:

```text
POST /v1/audio/speech
```

using the exact OpenAI-shaped payload.

The tester displays equivalent:

```text
curl
Python
JavaScript
```

requests.

This lets you copy the integration directly into your Voice Translate application later.

---

# 27. Swagger design

Expose:

```text
/docs
```

Swagger UI.

Also:

```text
/redoc
```

and:

```text
/openapi.json
```

Every endpoint must document:

```text
description
request schema
field descriptions
allowed values
defaults
examples
success example
400 example
422 example
429 example
500 example
503 example
```

---

# 28. WebSocket documentation

Swagger/OpenAPI does not provide a good interactive WebSocket tester.

So add:

```text
/docs/realtime
```

and preferably:

```text
/asyncapi.json
```

with AsyncAPI documentation.

GUI itself becomes the actual interactive WS debugger.

---

# 29. Error architecture

All JSON errors use one common structure:

```json
{
  "error": {
    "code": "INVALID_VOICE",
    "message": "Voice 'abc' is not available.",
    "type": "validation_error",
    "request_id": "req_a84df92",
    "retryable": false,
    "details": {
      "allowed": [
        "aria",
        "jason",
        "john",
        "leo",
        "sofia"
      ]
    }
  }
}
```

---

# 30. Error codes

Define at minimum:

```text
INVALID_REQUEST
EMPTY_TEXT
TEXT_TOO_LONG

INVALID_LANGUAGE
UNSUPPORTED_LANGUAGE

INVALID_VOICE
INVALID_FORMAT
INVALID_SAMPLE_RATE
INVALID_SPEED

MODEL_NOT_LOADED
MODEL_LOADING
MODEL_SWITCHING
MODEL_LOAD_FAILED

CODEC_NOT_READY

QUEUE_FULL
CONCURRENCY_LIMIT

SYNTHESIS_TIMEOUT
SYNTHESIS_CANCELLED
SYNTHESIS_FAILED

CUDA_OOM
CUDA_ERROR

ENCODER_FAILED
RESAMPLER_FAILED

WEBSOCKET_PROTOCOL_ERROR
WEBSOCKET_SESSION_NOT_FOUND

INTERNAL_ERROR
```

---

# 31. Correct HTTP statuses

```text
400 malformed request

404 unknown endpoint/model

409 conflicting model operation

422 unsupported language/voice/settings

429 server overloaded

500 unexpected synthesis failure

503 model unavailable/loading/OOM recovery

504 synthesis timeout
```

---

# 32. Streaming errors

WebSocket error:

```json
{
  "type": "error",
  "error": {
    "code": "QUEUE_FULL",
    "message": "Realtime synthesis queue is full.",
    "retryable": true,
    "request_id": "req_xxx"
  }
}
```

Never crash the entire WebSocket process because one request fails.

---

# 33. Scheduler

The scheduler is critical for realtime response.

Priority:

```text
Priority 0:
Live voice-agent streams

Priority 10:
normal /v1/audio/speech

Priority 20:
GUI tests

Priority 30:
benchmarks
```

Therefore a GUI benchmark can never delay a customer call unnecessarily.

---

# 34. Queue/backpressure

Config:

```yaml
scheduler:
  max_queue: 32
  realtime_priority: true
  cancel_on_disconnect: true
```

If full:

```text
429 QUEUE_FULL
```

Do not allow unbounded memory growth.

---

# 35. Model configuration

Initial production profile:

```yaml
model:
  id: magpie-tts-multilingual-357m
  revision: v2607

runtime:
  device: cuda:0
  precision: fp16
  batch_size: 1

server:
  host: 0.0.0.0
  port: 8092
  workers: 1
```

FP16 is the first profile I would benchmark for low VRAM.

FP32 remains the reference-quality profile.

BF16 is benchmarked rather than assumed better.

---

# 36. Additional optimization flags

GUI advanced panel can expose:

```text
torch.compile
CFG on/off
CFG scale
text normalization
phrase window
batch size
audio output sample rate
stream buffer size
```

But every experimental optimization requires:

```text
validation → warmup → self-test
```

before becoming available as default.

---

# 37. Pronunciation dictionary

This is particularly useful for the future Voice Translate application.

Magpie v2607 supports IPA-based pronunciation customization and code-switching mechanisms. ([Hugging Face][4])

Create GUI:

```text
Pronunciation Dictionary
```

Examples:

```text
Biolastic
GST
UPI
Siliguri
LiveKit
SKU
```

Fields:

```text
Word
Language
IPA pronunciation
Enabled
Test
```

Click:

```text
TEST
```

and hear before/after.

---

# 38. Text normalization

Enable by default.

The current Magpie model specifically includes normalization support for numbers, abbreviations and special characters across its supported languages. ([Hugging Face][1])

Testing GUI should include:

```text
₹1,450

15/08/2026

9876543210

Order #4821

GST 18%

10:30 AM
```

These are far more important for your voice agent than generic audiobook sentences.

---

# 39. Long text

Magpie's documented standard mode is intended for roughly up to 20 seconds of speech, while it also has a long-form sliding-window mode. ([Hugging Face][4])

API design:

```text
mode = auto
```

Server decides:

```text
short → standard
long → segmentation/long-form
```

For realtime agent traffic, the phrase streamer should normally keep requests far below this limit anyway.

---

# 40. Observability

Dashboard should expose live:

```text
GPU memory
GPU utilization
GPU temperature

CPU %
RAM

model state
model profile

active synthesis
active WebSockets
queue depth

TTFA
RTF

requests
errors
cancelled generations
```

No separate Prometheus installation is required initially.

But expose:

```text
/metrics
```

later for Prometheus compatibility.

---

# 41. Logging

Every request gets:

```text
request_id
session_id
```

Log:

```text
time
endpoint
language
voice
text length
stream yes/no
TTFA
generation time
audio duration
RTF
peak VRAM
status
error code
```

Don't log full customer text by default.

GUI can enable:

```text
Debug logging
```

temporarily.

---

# 42. Health endpoints

```text
GET /health
```

means:

```text
web server alive
```

`200` even if model isn't loaded.

---

```text
GET /ready
```

means:

```text
model loaded
codec loaded
warmup passed
synthesis available
```

Return `503` until ready.

---

# 43. System endpoint

```text
GET /api/system
```

Example:

```json
{
  "status": "ready",

  "server": {
    "version": "1.0.0"
  },

  "model": {
    "id": "magpie-tts-multilingual-357m",
    "revision": "v2607",
    "precision": "fp16"
  },

  "gpu": {
    "device": "cuda:0",
    "used_mb": 1920,
    "free_mb": 14300,
    "utilization": 22
  },

  "runtime": {
    "active_sessions": 1,
    "queue": 0
  }
}
```

All numbers should be runtime measurements.

---

# 44. GUI look and UX

Keep it a technical operations console, not a marketing website.

Left navigation:

```text
Magpie TTS

● Ready

Dashboard

Playground
Realtime Lab

Voices
Pronunciation

Models
Performance

API Tester
Swagger
Realtime Docs

Self Test
Logs
System
```

Top bar:

```text
MODEL: v2607
PROFILE: FP16
GPU: CUDA:0
VRAM: 2.1 / 16 GB
SESSIONS: 1
```

---

# 45. Installation architecture

Application should support:

```text
./install.sh
```

which performs:

```text
dependency validation
Python environment
NeMo installation
model download
codec download
frontend build
config creation
self-test
systemd creation
service startup
```

Final service:

```text
magpie-tts.service
```

Startup:

```text
0.0.0.0:8092
```

---

# 46. Deployment choice

For this particular GPU inference service, I prefer:

```text
systemd
+
Python venv
```

as the primary deployment.

Docker support can also exist.

Reason for the architecture:

```text
systemd
   ↓
single process
   ↓
direct CUDA access
   ↓
less deployment complexity
```

Docker remains useful for portability, but isn't mandatory.

---

# 47. No authentication

Per your requirement:

```text
API AUTH = NONE
GUI AUTH = NONE
WS AUTH = NONE
```

Server:

```text
0.0.0.0
```

However, because the GUI includes **model switching and administrative operations**, firewall access should be restricted to your LAN/application network. The application itself still has **zero authentication**.

---

# 48. Existing VoxCPM

**Do nothing to VoxCPM.**

Keep:

```text
VoxCPM Server
existing port
existing API
existing app integration
```

Completely untouched.

New:

```text
Magpie Server
:8092
```

---

# 49. Future Voice Translate architecture

Not part of this implementation, but we're deliberately designing the API so later you can have:

```text
Voice Translate Settings

Default TTS Engine:

○ VoxCPM
● Magpie
○ Custom OpenAI-compatible
```

Then:

```text
VoxCPM
Base URL: ...

Magpie
Base URL:
http://192.168.x.x:8092/v1
```

That future application only chooses providers.

It doesn't need to know how Magpie works internally.

---

# 50. Compatibility layer

Create this now inside the Magpie project:

```text
app/adapters/
├── openai.py
├── native.py
└── voxcpm_compat.py
```

`voxcpm_compat.py` remains isolated.

When the exact current Voice Translate → VoxCPM request contract is integrated later, only this adapter gets updated.

The Magpie engine does not change.

---

# 51. Performance presets

GUI should offer three named presets.

### Realtime

```text
FP16
batch 1
short phrase buffering
PCM output
priority scheduling
```

### Balanced

```text
FP16
larger phrase buffer
quality options enabled
```

### Reference

```text
FP32
full utterance
quality comparison
```

Then user can create:

```text
CUSTOM PROFILE
```

---

# 52. Test corpus built into GUI

Ship a small built-in test pack.

### Hindi

```text
नमस्ते सर, मैं आपकी कैसे सहायता कर सकता हूँ?

आपका ऑर्डर कल डिस्पैच हो जाएगा।
```

### English

```text
Your order has already been dispatched.

Please tell me your registered phone number.
```

### Hinglish

```text
Sir आपका order dispatch हो चुका है।

Payment अभी तक receive नहीं हुआ है।
```

### Numbers

```text
Your order number is 482913.

Total amount is ₹1,452.50.

Your OTP is 853921.
```

These are the tests that matter for the actual voice-agent use case.

---

# 53. Acceptance criteria

I would consider the project complete only when:

* Server binds to **`0.0.0.0`**
* GUI available on `/`
* Swagger available on `/docs`
* ReDoc available on `/redoc`
* OpenAPI JSON available
* OpenAI `/v1/audio/speech` works
* `/v1/models` works
* voice discovery works
* non-streaming synthesis works
* HTTP streaming works
* WebSocket streaming works
* incremental text works
* cancellation works
* Hindi works
* English works
* Hinglish test works
* WAV works
* PCM works
* MP3/OPUS transcoding works
* model remains loaded
* GUI can switch precision profiles
* failed profile automatically recovers
* GUI measures actual VRAM
* GUI measures TTFA
* GUI measures RTF
* GUI tests concurrent requests
* error handling is structured
* one-click full self-test works
* no API authentication exists
* VoxCPM remains untouched

---

## Final product architecture

```text
                    MAGPIE TTS SERVER
                       0.0.0.0:8092
                              │
       ┌──────────────────────┼─────────────────────┐
       │                      │                     │
       ▼                      ▼                     ▼
 Testing GUI             REST API              WebSocket
       │                      │                     │
       │              /v1/audio/speech        /v1/realtime
       │                      │                     │
       └──────────────────────┼─────────────────────┘
                              │
                         Scheduler
                              │
                      Phrase Streamer
                              │
                        Model Manager
                              │
                  ┌───────────┴───────────┐
                  │                       │
              Magpie 357M             NanoCodec
                  │
           selected profile
        FP32 / FP16 / BF16 /
         validated quantized
                  │
                  ▼
              PCM 22.05k
                  │
             Resampler /
              Encoder
                  │
       ┌──────────┼───────────┐
       ▼          ▼           ▼
      PCM        WAV        MP3/OPUS
```

### The most important product decisions

**Separate app:** yes.

**Separate from VoxCPM:** yes.

**Separate from Nemotron ASR:** yes.

**Bind `0.0.0.0`:** yes.

**No authentication:** yes.

**Testing GUI:** full-featured.

**Swagger/OpenAPI:** full.

**OpenAI-compatible endpoint:** yes.

**Realtime WebSocket:** yes.

**HTTP streaming:** yes.

**Model stays permanently loaded:** yes.

**Precision/quantization switchable from GUI:** yes, but only validated profiles become selectable.

**Default starting runtime:** **FP16**, benchmarked against FP32/BF16.

**Raw INT8/INT4:** architecture ready, but not falsely advertised as supported until we actually validate a conversion/runtime, because NVIDIA's current official Magpie repository doesn't publish those artifacts. ([Hugging Face][6])

This gives you a **self-contained TTS appliance** that later plugs into the Voice Translate application as another provider without disturbing the existing VoxCPM service.

[1]: https://huggingface.co/nvidia/magpie_tts_multilingual_357m/blob/main/README.md?utm_source=chatgpt.com "README.md · nvidia/magpie_tts_multilingual_357m at main"
[2]: https://platform.openai.com/docs/api-reference/audio/voice-consent-list?lang=curl&utm_source=chatgpt.com "Audio | OpenAI API Reference"
[3]: https://docs.nvidia.com/nim/speech/26.07.0/reference/api-references/tts/http-tts.html?utm_source=chatgpt.com "TTS HTTP REST API Reference — NVIDIA Speech NIM Microservices"
[4]: https://huggingface.co/nvidia/magpie_tts_multilingual_357m?utm_source=chatgpt.com "nvidia/magpie_tts_multilingual_357m · Hugging Face"
[5]: https://docs.nvidia.com/nim/speech/latest/reference/api-references/tts/realtime-tts.html?utm_source=chatgpt.com "Realtime API Reference — NVIDIA Speech NIM Microservices"
[6]: https://huggingface.co/nvidia/magpie_tts_multilingual_357m/blob/main/magpie_tts_multilingual_357m.nemo?utm_source=chatgpt.com "magpie_tts_multilingual_357m.nemo · nvidia/magpie_tts_multilingual_357m at main"
