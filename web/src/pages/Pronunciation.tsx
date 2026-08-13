import { useEffect, useState } from 'react'
import { api, synthesize } from '../api'
import { AudioPlayer } from '../components/AudioPlayer'
import { Card, Badge } from '../components/ui'

interface Entry { word: string; language: string; ipa: string; enabled: boolean }

const SUGGESTED = ['Biolastic', 'GST', 'UPI', 'Siliguri', 'LiveKit', 'SKU']

export function Pronunciation() {
  const [entries, setEntries] = useState<Entry[]>([])
  const [word, setWord] = useState('')
  const [language, setLanguage] = useState('en')
  const [ipa, setIpa] = useState('')
  const [enabled, setEnabled] = useState(true)
  const [testResult, setTestResult] = useState<{ url: string; name: string } | null>(null)
  const [testWord, setTestWord] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const load = () => api('/api/tts/pronunciation').then((r) => setEntries(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  const save = async () => {
    if (!word.trim()) return
    await api('/api/tts/pronunciation', {
      method: 'POST',
      body: JSON.stringify({ word, language, ipa, enabled }),
    })
    setWord(''); setIpa(''); setMessage(`Saved "${word}"`)
    load()
  }

  const remove = async (w: string, l: string) => {
    await api(`/api/tts/pronunciation/${encodeURIComponent(w)}?language=${l}`, { method: 'DELETE' })
    load()
  }

  const test = async (w: string, l: string) => {
    setBusy(true); setTestWord(w)
    try {
      const r = await synthesize({ text: w, language: l, voice: 'aria', format: 'wav' })
      if (testResult) URL.revokeObjectURL(testResult.url)
      setTestResult({ url: r.url, name: `pron-${w}.wav` })
    } catch (e: any) {
      setMessage(`test failed: ${e.message}`)
    }
    setBusy(false)
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">Pronunciation Dictionary</h1>
      <Card title="New entry (IPA via | p a t | syntax)">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <input className="input" placeholder="Word" value={word} onChange={(e) => setWord(e.target.value)} />
          <select className="input" value={language} onChange={(e) => setLanguage(e.target.value)}>
            {['en', 'hi'].map((l) => <option key={l}>{l}</option>)}
          </select>
          <input className="input md:col-span-2" placeholder="IPA: e.g. b aɪ oʊ l æ s t ɪ k" value={ipa} onChange={(e) => setIpa(e.target.value)} />
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1 text-xs text-zinc-400">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="h-4 w-4 accent-indigo-500" />
              enabled
            </label>
            <button className="btn-primary" onClick={save}>Save</button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTED.map((s) => (
            <button key={s} className="btn text-xs" onClick={() => setWord(s)}>{s}</button>
          ))}
        </div>
      </Card>
      {message && <div className="text-sm text-emerald-400">{message}</div>}
      <Card title={`Entries (${entries.length})`}>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-zinc-500">
              <th className="pb-2">Word</th><th className="pb-2">Language</th>
              <th className="pb-2">IPA</th><th className="pb-2">Enabled</th><th className="pb-2">Actions</th>
            </tr>
          </thead>
          <tbody className="mono">
            {entries.map((e) => (
              <tr key={`${e.word}-${e.language}`} className="border-t border-zinc-800">
                <td className="py-2">{e.word}</td>
                <td className="py-2">{e.language}</td>
                <td className="py-2 text-zinc-400">| {e.ipa} |</td>
                <td className="py-2">{e.enabled ? <Badge color="green">on</Badge> : <Badge>off</Badge>}</td>
                <td className="py-2 flex gap-2">
                  <button className="btn text-xs" onClick={() => test(e.word, e.language)} disabled={busy}>
                    {testWord === e.word && busy ? '…' : 'TEST'}
                  </button>
                  <button className="btn text-xs" onClick={() => remove(e.word, e.language)}>✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {testResult && (
          <div className="mt-4">
            <AudioPlayer src={testResult.url} name={testResult.name} />
          </div>
        )}
      </Card>
    </div>
  )
}
