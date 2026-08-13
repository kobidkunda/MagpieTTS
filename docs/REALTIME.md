# Realtime WebSocket API

Stream speech phrase-by-phrase for low-latency voice agents.

Connection: `ws://<host>:8092/v1/realtime?intent=synthesize`

All messages are JSON. Audio is base64-encoded inside `audio.chunk` events.

## Lifecycle

```text
CONNECT
  ↓
session.created            (server → client)
  ↓
session.update             (client → server)
  ↓
session.updated            (server → client)
  ↓
input_text.append  ×N      (client → server, stream tokens as LLM produces them)
  ↓
input_text.commit          (client → server)
  ↓
response.created           (server → client)
  ↓
audio.chunk  ×N            (server → client)
  ↓
response.completed         (server → client)
```

## Client → server events

### `session.update`

Configure the session.

```json
{
  "type": "session.update",
  "session": {
    "voice": "aria",
    "language": "hi",
    "format": "pcm",
    "sample_rate": 22050,
    "speed": 1.0,
    "text_normalization": false,
    "cfg_enabled": true,
    "cfg_scale": 2.5,
    "priority": 0,
    "mode": "auto"
  }
}
```

| Field | Default | Description |
|-------|---------|-------------|
| `voice` | `aria` | `aria`, `jason`, `john`, `leo`, `sofia` |
| `language` | `en` | 12 languages (`hi`, `en`, …) |
| `format` | `pcm` | `pcm`, `wav`, `mp3`, `opus`, `flac`, `aac` |
| `sample_rate` | `22050` | `8000`, `16000`, `22050`, `24000`, `48000` |
| `speed` | `1.0` | `0.25`–`4.0` |
| `text_normalization` | `false` | Apply text normalization |
| `cfg_enabled` | `true` | Classifier-free guidance |
| `cfg_scale` | `2.5` | CFG scale |
| `priority` | `0` | Scheduler priority `0`–`30` |
| `mode` | `auto` | `auto`, `standard`, `long` |

### `input_text.append`

Append a text token/fragment to the buffer. Fragments may split words — the
phrase buffer concatenates them verbatim and only flushes at phrase boundaries.

```json
{ "type": "input_text.append", "text": "आपका " }
```

### `input_text.commit`

Flush all buffered phrases to synthesis.

```json
{ "type": "input_text.commit" }
```

### `response.cancel`

Cancel queued/active synthesis (barge-in).

```json
{ "type": "response.cancel" }
```

### `ping`

```json
{ "type": "ping" }
```

## Server → client events

| Event | Description |
|-------|-------------|
| `session.created` | Sent on connect |
| `session.updated` | Confirms `session.update` with the applied config |
| `response.created` | A synthesis response started |
| `audio.chunk` | Base64 audio chunk (`{ "type": "audio.chunk", "data": "<b64>" }`) |
| `response.completed` | Synthesis finished (`{ "duration_s": …, "ttfa_ms": … }`) |
| `response.cancelled` | Confirms cancellation (`{ "cancelled_jobs": N }`) |
| `error` | Protocol/validation/synthesis error |
| `pong` | Reply to `ping` |

## Phrase streaming engine

Tokens are buffered and flushed at sentence boundaries (`.`, `?`, `!`, `,`, `;`,
`:`, Hindi danda `।`, newline) or after the configured word/time thresholds.
This yields low time-to-first-audio without waiting for a full LLM response.

Defaults (tunable via `configs/server.yaml`):

```yaml
phrase:
  min_words: 3
  preferred_words: 8
  max_words: 18
  soft_timeout_ms: 120
  hard_timeout_ms: 250
```

## Examples

### Python

```python
import asyncio, base64, json, websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:8092/v1/realtime?intent=synthesize") as ws:
        await ws.recv()  # session.created
        await ws.send(json.dumps({"type": "session.update", "session": {
            "voice": "aria", "language": "hi", "format": "pcm", "sample_rate": 22050}}))
        await ws.recv()  # session.updated

        for tok in ["जी ", "सर, ", "आपका ", "order ", "dispatch हो चुका है।"]:
            await ws.send(json.dumps({"type": "input_text.append", "text": tok}))
        await ws.send(json.dumps({"type": "input_text.commit"}))

        while True:
            msg = json.loads(await ws.recv())
            if msg["type"] == "audio.chunk":
                pcm = base64.b64decode(msg["data"])
                # play / stream pcm immediately
            elif msg["type"] == "response.completed":
                break

asyncio.run(main())
```

### JavaScript (browser)

```js
const ws = new WebSocket("ws://HOST:8092/v1/realtime?intent=synthesize");

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === "session.created") {
    ws.send(JSON.stringify({ type: "session.update", session: {
      voice: "aria", language: "en", format: "wav", sample_rate: 22050 } }));
  } else if (msg.type === "session.updated") {
    ws.send(JSON.stringify({ type: "input_text.append", text: "Hello " }));
    ws.send(JSON.stringify({ type: "input_text.append", text: "world." }));
    ws.send(JSON.stringify({ type: "input_text.commit" }));
  } else if (msg.type === "audio.chunk") {
    // base64 WAV chunk → queue for playback
    const bytes = Uint8Array.from(atob(msg.data), c => c.charCodeAt(0));
    enqueueAudio(bytes);
  }
};
```
