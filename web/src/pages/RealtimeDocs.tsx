import { Card } from '../components/ui'

const LIFECYCLE = `CONNECT  ws://SERVER:8092/v1/realtime?intent=synthesize
  |
  |  { "type": "session.created" }               <- server
  |
  |  { "type": "session.update", "session": { voice, language, format, sample_rate, speed } }
  |  { "type": "session.updated" }               <- server
  |
  |  { "type": "input_text.append", "text": "आपका " }   (streamed LLM tokens)
  |  { "type": "input_text.append", "text": "order number " }
  |  { "type": "input_text.append", "text": "4827 है।" }
  |  { "type": "input_text.commit" }
  |
  |  { "type": "response.created" }              <- server
  |  { "type": "audio.chunk", "data": "<base64>", "format": "pcm", "sample_rate": 22050 }  xN
  |  { "type": "response.completed" }            <- server
  |
  |  { "type": "response.cancel" }               (barge-in: cancels queued phrases)
  |  { "type": "response.cancelled" }            <- server
`

const CLIENT_EVENTS = [
  { name: 'session.update', payload: `{
  "type": "session.update",
  "session": {
    "voice": "aria",
    "language": "hi",
    "format": "pcm",
    "sample_rate": 22050,
    "speed": 1.0,
    "text_normalization": true,
    "cfg_enabled": false,
    "cfg_scale": 2.5,
    "phrase": {
      "min_words": 3, "preferred_words": 8, "max_words": 18,
      "soft_timeout_ms": 120, "hard_timeout_ms": 250
    }
  }
}` },
  { name: 'input_text.append', payload: `{ "type": "input_text.append", "text": "आपका " }` },
  { name: 'input_text.commit', payload: `{ "type": "input_text.commit" }` },
  { name: 'response.cancel', payload: `{ "type": "response.cancel" }` },
  { name: 'ping', payload: `{ "type": "ping" }` },
]

const SERVER_EVENTS = [
  { name: 'session.created', payload: `{ "type": "session.created", "session_id": "sess_xxx" }` },
  { name: 'session.updated', payload: `{ "type": "session.updated", "session": { ... } }` },
  { name: 'response.created', payload: `{ "type": "response.created", "session_id": "sess_xxx" }` },
  { name: 'audio.chunk', payload: `{
  "type": "audio.chunk",
  "session_id": "sess_xxx",
  "data": "<base64 PCM>",
  "format": "pcm",
  "sample_rate": 22050,
  "chunk_index": 0
}` },
  { name: 'response.completed', payload: `{ "type": "response.completed", "session_id": "sess_xxx", "duration_s": 2.31, "ttfa_ms": 183.4 }` },
  { name: 'response.cancelled', payload: `{ "type": "response.cancelled", "session_id": "sess_xxx", "cancelled_jobs": 2 }` },
  { name: 'error', payload: `{
  "type": "error",
  "error": {
    "code": "QUEUE_FULL",
    "message": "Realtime synthesis queue is full.",
    "retryable": true,
    "request_id": "req_xxx",
    "session_id": "sess_xxx"
  }
}` },
]

export function RealtimeDocs() {
  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">Realtime WebSocket Protocol</h1>
      <Card title="Connection lifecycle">
        <pre className="mono text-xs text-zinc-300 overflow-x-auto">{LIFECYCLE}</pre>
      </Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Client events">
          <div className="space-y-3">
            {CLIENT_EVENTS.map((e) => (
              <div key={e.name}>
                <div className="text-sm font-semibold text-sky-400">→ {e.name}</div>
                <pre className="mono text-[11px] text-zinc-400 bg-zinc-950 rounded p-2 overflow-x-auto">{e.payload}</pre>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Server events">
          <div className="space-y-3">
            {SERVER_EVENTS.map((e) => (
              <div key={e.name}>
                <div className="text-sm font-semibold text-emerald-400">← {e.name}</div>
                <pre className="mono text-[11px] text-zinc-400 bg-zinc-950 rounded p-2 overflow-x-auto">{e.payload}</pre>
              </div>
            ))}
          </div>
        </Card>
      </div>
      <Card title="Phrase streaming">
        <p className="text-sm text-zinc-400">
          Incremental <code className="mono text-sky-400">input_text.append</code> tokens are held in a
          phrase buffer. Synthesis starts as soon as the buffer satisfies the phrase rules
          (min/preferred/max words, soft/hard timeouts, sentence punctuation). This gives low
          perceived time-to-first-audio without waiting for the full LLM response.
        </p>
      </Card>
    </div>
  )
}
