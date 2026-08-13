import { useState } from 'react'
import { synthesize } from '../api'
import { AudioPlayer } from '../components/AudioPlayer'
import { Card, Badge, Spinner } from '../components/ui'

const VOICES = [
  { id: 'aria', name: 'Aria', gender: 'female' },
  { id: 'jason', name: 'Jason', gender: 'male' },
  { id: 'john', name: 'John', gender: 'male' },
  { id: 'leo', name: 'Leo', gender: 'male' },
  { id: 'sofia', name: 'Sofia', gender: 'female' },
]

const SAMPLE_TEXT = 'नमस्ते सर, आपका order number 482913 dispatch हो चुका है। Total amount ₹1,452.50 है।'

export function Voices() {
  const [language, setLanguage] = useState('hi')
  const [text, setText] = useState(SAMPLE_TEXT)
  const [results, setResults] = useState<Record<string, { url: string; name: string } | null>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const runAll = async () => {
    setBusy(true); setError(null)
    for (const v of VOICES) {
      try {
        const r = await synthesize({ text, language, voice: v.id, format: 'wav' })
        if (results[v.id]) URL.revokeObjectURL(results[v.id]!.url)
        setResults((prev) => ({ ...prev, [v.id]: { url: r.url, name: `voice-${v.id}.wav` } }))
      } catch (e: any) {
        setError(`Voice ${v.id}: ${e.message}`)
      }
    }
    setBusy(false)
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">Voice Matrix</h1>
      <Card title="Same text through every voice">
        <textarea className="input h-24" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-3 flex gap-3 items-center">
          <select className="input w-40" value={language} onChange={(e) => setLanguage(e.target.value)}>
            {['ar', 'zh', 'en', 'fr', 'de', 'hi', 'it', 'ja', 'ko', 'pt', 'es', 'vi'].map((l) => <option key={l}>{l}</option>)}
          </select>
          <button className="btn-primary" onClick={runAll} disabled={busy}>Generate all 5 voices</button>
          {busy && <Spinner label="generating matrix" />}
        </div>
      </Card>
      {error && <div className="text-red-400 text-sm">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {VOICES.map((v) => (
          <Card key={v.id} title={
            <span className="flex items-center gap-2">
              {v.name} <Badge color="blue">{v.gender}</Badge>
            </span>
          }>
            {results[v.id] ? (
              <AudioPlayer src={results[v.id]!.url} name={results[v.id]!.name} />
            ) : (
              <div className="text-sm text-zinc-600">Not generated yet.</div>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
