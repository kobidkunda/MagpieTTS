import { useEffect, useState } from 'react'
import { api, synthesize } from '../api'
import { AudioPlayer } from '../components/AudioPlayer'
import { Card, Field, Badge, Spinner } from '../components/ui'

const TEST_SENTENCES = [
  { lang: 'hi', text: 'नमस्ते सर, मैं आपकी कैसे सहायता कर सकता हूँ?' },
  { lang: 'hi', text: 'आपका ऑर्डर कल डिस्पैच हो जाएगा।' },
  { lang: 'en', text: 'Your order has already been dispatched.' },
  { lang: 'en', text: 'Please tell me your registered phone number.' },
  { lang: 'hi', text: 'Sir आपका order dispatch हो चुका है।' },
  { lang: 'hi', text: 'Payment अभी तक receive नहीं हुआ है।' },
  { lang: 'hi', text: 'Your order number is 482913.' },
  { lang: 'hi', text: 'Total amount is ₹1,452.50.' },
  { lang: 'hi', text: 'Your OTP is 853921.' },
]

const FORMATS = ['wav', 'pcm', 'mp3', 'opus', 'flac', 'aac']
const RATES = [8000, 16000, 22050, 24000, 48000]

export function Playground() {
  const [languages, setLanguages] = useState<string[]>([])
  const [voices, setVoices] = useState<{ id: string; name: string }[]>([])
  const [text, setText] = useState('नमस्ते सर, मैं आपकी कैसे सहायता कर सकता हूँ?')
  const [language, setLanguage] = useState('hi')
  const [voice, setVoice] = useState('aria')
  const [speed, setSpeed] = useState(1.0)
  const [format, setFormat] = useState('wav')
  const [rate, setRate] = useState(22050)
  const [tn, setTn] = useState(true)
  const [cfg, setCfg] = useState(false)
  const [cfgScale, setCfgScale] = useState(2.5)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ url: string; name: string } | null>(null)
  const [metrics, setMetrics] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api('/api/languages').then((r) => setLanguages(r.data.map((l: any) => l.id))).catch(() => {})
    api('/v1/audio/voices').then((r) => setVoices(r.data.map((v: any) => ({ id: v.id, name: v.name })))).catch(() => {})
  }, [])

  const run = async () => {
    setBusy(true); setError(null); setMetrics(null)
    if (result) URL.revokeObjectURL(result.url)
    setResult(null)
    try {
      const t0 = performance.now()
      const r = await synthesize({ text, language, voice, format, speed, sampleRate: rate, tn, cfg, cfgScale })
      const elapsed = performance.now() - t0
      setResult({ url: r.url, name: `magpie-${language}-${voice}.${format === 'pcm' ? 'pcm' : format}` })
      setMetrics({ total_ms: elapsed.toFixed(0), bytes: r.blob.size })
    } catch (e: any) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">TTS Playground</h1>
      <Card title="Input">
        <textarea
          className="input h-28"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type text to synthesize…"
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {TEST_SENTENCES.map((s, i) => (
            <button key={i} className="btn text-xs" onClick={() => { setText(s.text); setLanguage(s.lang) }}>
              {s.lang === 'hi' && !/[a-zA-Z]/.test(s.text) ? 'हिंदी' : s.lang === 'hi' ? 'Hinglish' : 'English'}
            </button>
          ))}
        </div>
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="Language">
            <select className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
              {languages.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </Field>
          <Field label="Voice">
            <select className="input" value={voice} onChange={(e) => setVoice(e.target.value)}>
              {voices.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          </Field>
          <Field label="Format">
            <select className="input" value={format} onChange={(e) => setFormat(e.target.value)}>
              {FORMATS.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </Field>
          <Field label="Sample rate">
            <select className="input" value={rate} onChange={(e) => setRate(Number(e.target.value))}>
              {RATES.map((r) => <option key={r} value={r}>{r} Hz</option>)}
            </select>
          </Field>
          <Field label={`Speed: ${speed.toFixed(2)}x`}>
            <input type="range" min={0.25} max={4} step={0.05} value={speed}
                   onChange={(e) => setSpeed(Number(e.target.value))} className="w-full" />
          </Field>
          <Field label="Text normalization">
            <input type="checkbox" checked={tn} onChange={(e) => setTn(e.target.checked)}
                   className="h-5 w-5 accent-indigo-500" />
          </Field>
          <Field label={`CFG ${cfg ? 'on' : 'off'}`}>
            <input type="checkbox" checked={cfg} onChange={(e) => setCfg(e.target.checked)}
                   className="h-5 w-5 accent-indigo-500" />
          </Field>
          <Field label={`CFG scale: ${cfgScale}`}>
            <input type="range" min={1} max={10} step={0.1} value={cfgScale} disabled={!cfg}
                   onChange={(e) => setCfgScale(Number(e.target.value))} className="w-full" />
          </Field>
        </div>
        <div className="mt-4 flex gap-2">
          <button className="btn-primary" onClick={run} disabled={busy || !text.trim()}>
            {busy ? 'Generating…' : 'Generate'}
          </button>
          {busy && <Spinner label="synthesizing" />}
        </div>
      </Card>
      {error && (
        <Card title="Error">
          <div className="text-red-400 text-sm">{error}</div>
        </Card>
      )}
      {metrics && (
        <div className="flex flex-wrap gap-3">
          <Badge color="green">total {metrics.total_ms} ms</Badge>
          <Badge color="blue">{metrics.bytes} bytes</Badge>
        </div>
      )}
      {result && (
        <Card title="Result">
          <AudioPlayer src={result.url} name={result.name} />
        </Card>
      )}
    </div>
  )
}
