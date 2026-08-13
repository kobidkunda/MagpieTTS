import { useEffect, useRef, useState } from 'react'
import { wsUrl } from '../api'
import { AudioPlayer } from '../components/AudioPlayer'
import { Card, Field, Badge } from '../components/ui'

const DEMO_TEXT =
  'जी सर, आपका order dispatch हो चुका है। हमारा delivery partner कल सुबह 10 बजे आपके पते पर पहुंचेगा। आपका order number 482913 है। धन्यवाद।'

export function RealtimeLab() {
  const wsRef = useRef<WebSocket | null>(null)
  const clipRef = useRef<Uint8Array[]>([])
  const [connected, setConnected] = useState(false)
  const [text, setText] = useState(DEMO_TEXT)
  const [tokenRate, setTokenRate] = useState(6)
  const [language, setLanguage] = useState('hi')
  const [voice, setVoice] = useState('aria')
  const [minWords, setMinWords] = useState(3)
  const [prefWords, setPrefWords] = useState(8)
  const [maxWords, setMaxWords] = useState(18)
  const [softT, setSoftT] = useState(120)
  const [hardT, setHardT] = useState(250)
  const [log, setLog] = useState<{ t: number; dir: string; msg: string }[]>([])
  const [clips, setClips] = useState<{ id: number; url: string; duration: number }[]>([])
  const clipSeqRef = useRef(0)
  const [streaming, setStreaming] = useState(false)
  const [chunkCount, setChunkCount] = useState(0)

  const pushLog = (dir: string, msg: string) => {
    setLog((prev) => [...prev.slice(-150), { t: performance.now(), dir, msg }])
  }

  useEffect(() => () => { wsRef.current?.close() }, [])

  const connect = () => {
    wsRef.current?.close()
    const ws = new WebSocket(wsUrl('/v1/realtime?intent=synthesize'))
    wsRef.current = ws
    ws.onopen = () => {
      setConnected(true)
      ws.send(JSON.stringify({
        type: 'session.update',
        session: {
          voice, language, format: 'pcm', sample_rate: 22050, speed: 1.0,
          text_normalization: false,
          phrase: { min_words: minWords, preferred_words: prefWords, max_words: maxWords,
                    soft_timeout_ms: softT, hard_timeout_ms: hardT },
        },
      }))
    }
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'session.created' || msg.type === 'session.updated') {
        pushLog('←', msg.type)
      } else if (msg.type === 'response.created') {
        clipRef.current = []
        pushLog('←', 'response.created (new phrase)')
      } else if (msg.type === 'audio.chunk') {
        clipRef.current.push(Uint8Array.from(atob(msg.data), (c) => c.charCodeAt(0)))
        setChunkCount((n) => n + 1)
        pushLog('←', `audio.chunk #${msg.chunk_index}`)
      } else if (msg.type === 'response.completed') {
        pushLog('←', `response.completed (${msg.duration_s}s, TTFA ${msg.ttfa_ms}ms)`)
        finalizeClip(msg.duration_s ?? 0)
      } else if (msg.type === 'response.cancelled') {
        pushLog('←', 'response.cancelled')
        clipRef.current = []
      } else if (msg.type === 'error') {
        pushLog('←', `error: ${msg.error?.code} ${msg.error?.message}`)
      } else {
        pushLog('←', msg.type)
      }
    }
    ws.onclose = () => { setConnected(false); pushLog('•', 'disconnected') }
    ws.onerror = () => pushLog('•', 'ws error')
  }

  const finalizeClip = (duration: number) => {
    const pcm = new Uint8Array((clipRef.current as Uint8Array[]).reduce((n, a) => n + a.length, 0))
    let off = 0
    for (const a of clipRef.current as Uint8Array[]) { pcm.set(a, off); off += a.length }
    clipRef.current = []
    if (pcm.length > 0) {
      const url = URL.createObjectURL(new Blob([wavFromPcm(pcm, 22050)], { type: 'audio/wav' }))
      setClips((prev) => [...prev, { id: ++clipSeqRef.current, url, duration }])
    }
  }

  const wavFromPcm = (pcm: Uint8Array, rate: number) => {
    const buf = new ArrayBuffer(44 + pcm.length)
    const v = new DataView(buf)
    const w = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)) }
    w(0, 'RIFF'); v.setUint32(4, 36 + pcm.length, true); w(8, 'WAVE')
    w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true)
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true)
    w(36, 'data'); v.setUint32(40, pcm.length, true)
    new Uint8Array(buf).set(pcm, 44)
    return buf
  }

  const startStream = async () => {
    connect()
    setStreaming(true)
    setLog([])
    setClips([])
    setChunkCount(0)
    clipRef.current = []
    const ws = wsRef.current
    if (!ws) return
    if (ws.readyState !== WebSocket.OPEN) {
      let opened = false
      await new Promise<void>((resolve) => {
        const t = setTimeout(() => resolve(), 5000)
        ws.onopen = () => { opened = true; clearTimeout(t); resolve() }
      })
      if (!opened) {
        pushLog('•', 'websocket did not open')
        setStreaming(false)
        return
      }
    }
    // simulate Gemini token streaming
    let i = 0
    while (i < text.length) {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) break
      const step = tokenRate
      const chunk = text.slice(i, i + step)
      pushLog('→', `input_text.append "${chunk}"`)
      wsRef.current.send(JSON.stringify({ type: 'input_text.append', text: chunk }))
      i += step
      await new Promise((r) => setTimeout(r, 40))
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      pushLog('→', 'input_text.commit')
      wsRef.current.send(JSON.stringify({ type: 'input_text.commit' }))
    }
    setStreaming(false)
  }

  const cancel = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      pushLog('→', 'response.cancel (barge-in)')
      wsRef.current.send(JSON.stringify({ type: 'response.cancel' }))
    }
  }

  const disconnect = () => {
    wsRef.current?.close()
    setConnected(false)
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">Realtime Streaming Lab</h1>
      <Card title="Configuration">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="Voice">
            <select className="input" value={voice} onChange={(e) => setVoice(e.target.value)}>
              {['aria', 'jason', 'john', 'leo', 'sofia'].map((v) => <option key={v}>{v}</option>)}
            </select>
          </Field>
          <Field label="Language">
            <select className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
              {['ar', 'zh', 'en', 'fr', 'de', 'hi', 'it', 'ja', 'ko', 'pt', 'es', 'vi'].map((l) => <option key={l}>{l}</option>)}
            </select>
          </Field>
          <Field label="Token rate (chars/step)">
            <input type="number" min={1} max={50} className="input" value={tokenRate}
                   onChange={(e) => setTokenRate(Number(e.target.value))} />
          </Field>
        </div>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-4">
          <Field label="Min words">
            <input type="number" className="input" value={minWords} onChange={(e) => setMinWords(Number(e.target.value))} />
          </Field>
          <Field label="Preferred words">
            <input type="number" className="input" value={prefWords} onChange={(e) => setPrefWords(Number(e.target.value))} />
          </Field>
          <Field label="Max words">
            <input type="number" className="input" value={maxWords} onChange={(e) => setMaxWords(Number(e.target.value))} />
          </Field>
          <Field label="Soft timeout (ms)">
            <input type="number" className="input" value={softT} onChange={(e) => setSoftT(Number(e.target.value))} />
          </Field>
          <Field label="Hard timeout (ms)">
            <input type="number" className="input" value={hardT} onChange={(e) => setHardT(Number(e.target.value))} />
          </Field>
        </div>
      </Card>

      <Card title="Simulate Gemini streaming">
        <textarea className="input h-24" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-3 flex gap-2 flex-wrap">
          <button className="btn-primary" onClick={startStream} disabled={streaming}>▶ Start</button>
          <button className="btn-danger" onClick={cancel} disabled={!connected}>✕ Cancel (barge-in)</button>
          <button className="btn" onClick={disconnect} disabled={!connected}>Disconnect</button>
          {connected && <Badge color="green">WS connected</Badge>}
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Event timeline">
          <div className="h-72 overflow-y-auto mono text-xs space-y-0.5">
            {log.length === 0 && <div className="text-zinc-600">No events yet. Press Start.</div>}
            {log.map((l, i) => (
              <div key={i} className={l.dir === '→' ? 'text-sky-400' : l.dir === '←' ? 'text-emerald-400' : 'text-zinc-500'}>
                {l.dir} {l.msg}
              </div>
            ))}
          </div>
        </Card>
        <Card title="Received audio">
          {clips.length === 0 ? (
            <div className="text-zinc-600 text-sm">Audio chunks will be assembled here.</div>
          ) : (
            <div className="space-y-2">
              {clips.map((c, i) => (
                <div key={c.id} className="flex items-center gap-2">
                  <span className="mono text-xs text-zinc-500 w-24 shrink-0">phrase {i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <AudioPlayer src={c.url} name={`phrase-${i + 1}.wav`} />
                  </div>
                  <span className="mono text-xs text-zinc-500 shrink-0">{c.duration.toFixed(1)}s</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-2 text-xs text-zinc-500">
            PCM 22.05 kHz chunks assembled client-side into per-phrase playable WAV clips ({chunkCount} chunks received).
          </div>
        </Card>
      </div>
    </div>
  )
}
