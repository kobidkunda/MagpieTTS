import { useState } from 'react'
import { Card, Badge } from '../components/ui'

const ENDPOINTS = [
  { method: 'GET', path: '/v1/models' },
  { method: 'GET', path: '/v1/audio/voices' },
  { method: 'GET', path: '/api/languages' },
  { method: 'POST', path: '/v1/audio/speech' },
  { method: 'POST', path: '/api/tts/generate' },
  { method: 'POST', path: '/api/profiles/switch' },
  { method: 'POST', path: '/api/benchmark' },
  { method: 'GET', path: '/api/system' },
]

const DEFAULT_BODY = JSON.stringify({
  model: 'magpie-tts-multilingual-357m',
  input: 'नमस्ते, यह एक API test है।',
  voice: 'aria',
  language: 'hi',
  response_format: 'wav',
}, null, 2)

const CURL_TEMPLATE = (method: string, path: string, body: string) =>
  `curl -X ${method} http://<server>:8092${path} \\\n  -H "Content-Type: application/json" \\\n  -d '${body.replace(/\n/g, ' ')}'`

const PY_TEMPLATE = (method: string, path: string, body: string) =>
  `import httpx, json

r = httpx.request(
    method="${method}",
    url="http://<server>:8092${path}",
    json=json.loads('''${body.replace(/'/g, "\\'")}'''),
)
print(r.status_code, r.content[:200])`

const JS_TEMPLATE = (method: string, path: string, body: string) =>
  `const res = await fetch("http://<server>:8092${path}", {
  method: "${method}",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(${body}),
});
console.log(res.status, await res.arrayBuffer());`

export function ApiTester() {
  const [path, setPath] = useState('/v1/audio/speech')
  const [method, setMethod] = useState('POST')
  const [body, setBody] = useState(DEFAULT_BODY)
  const [status, setStatus] = useState<number | null>(null)
  const [resp, setResp] = useState<string>('')
  const [duration, setDuration] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)

  const send = async () => {
    setBusy(true); setResp('')
    try {
      const t0 = performance.now()
      const res = await fetch(path, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: method === 'GET' ? undefined : body,
      })
      const ms = performance.now() - t0
      setStatus(res.status)
      setDuration(ms)
      const ct = res.headers.get('content-type') || ''
      const buf = await res.arrayBuffer()
      if (ct.includes('json')) {
        setResp(JSON.stringify(JSON.parse(new TextDecoder().decode(buf)), null, 2))
      } else {
        setResp(`[audio] ${buf.byteLength} bytes, content-type: ${ct}`)
      }
    } catch (e: any) {
      setStatus(-1)
      setResp(String(e))
    }
    setBusy(false)
  }

  const statusColor = status === null ? 'zinc' : status < 400 ? 'green' : status === 429 ? 'amber' : 'red'

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">API Tester</h1>
      <Card title="Request">
        <div className="flex gap-2">
          <select className="input w-28" value={method} onChange={(e) => setMethod(e.target.value)}>
            {['GET', 'POST', 'DELETE'].map((m) => <option key={m}>{m}</option>)}
          </select>
          <select className="input flex-1" value={path} onChange={(e) => setPath(e.target.value)}>
            {ENDPOINTS.filter((e) => e.method === method || true).map((e) => (
              <option key={e.path}>{e.path}</option>
            ))}
            <option value="/v1/audio/cancel">/v1/audio/cancel</option>
            <option value="/api/selftest">/api/selftest (POST)</option>
            <option value="/api/profiles">/api/profiles</option>
          </select>
          <button className="btn-primary" onClick={send} disabled={busy}>{busy ? '…' : 'Send'}</button>
        </div>
        {method !== 'GET' && (
          <textarea className="input mt-3 h-44 mono text-xs" value={body} onChange={(e) => setBody(e.target.value)} />
        )}
        <div className="mt-2 flex items-center gap-3">
          {status !== null && <Badge color={statusColor}>{status} · {duration?.toFixed(0)} ms</Badge>}
        </div>
      </Card>
      {resp && (
        <Card title="Response">
          <pre className="mono text-xs text-zinc-300 overflow-x-auto max-h-96 overflow-y-auto">{resp}</pre>
        </Card>
      )}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card title="Equivalent curl">
          <pre className="mono text-[11px] text-zinc-400 overflow-x-auto whitespace-pre-wrap">{CURL_TEMPLATE(method, path, body)}</pre>
        </Card>
        <Card title="Equivalent Python">
          <pre className="mono text-[11px] text-zinc-400 overflow-x-auto whitespace-pre-wrap">{PY_TEMPLATE(method, path, body)}</pre>
        </Card>
        <Card title="Equivalent JavaScript">
          <pre className="mono text-[11px] text-zinc-400 overflow-x-auto whitespace-pre-wrap">{JS_TEMPLATE(method, path, body)}</pre>
        </Card>
      </div>
    </div>
  )
}
