import { useState } from 'react'
import { api } from '../api'
import { Card, Badge, Spinner } from '../components/ui'

const TEST_NAMES: Record<string, string> = {
  test_health: 'Health',
  test_ready: 'Ready state',
  test_model_list: 'Model list',
  test_voice_list: 'Voice list',
  test_en_generation: 'English generation',
  test_hi_generation: 'Hindi generation',
  test_hinglish: 'Hinglish',
  test_wav: 'WAV',
  test_pcm: 'PCM',
  test_mp3: 'MP3',
  test_opus: 'OPUS',
  test_http_stream: 'HTTP streaming',
  test_ws_stream: 'WebSocket streaming',
  test_cancellation: 'Cancellation',
  test_profile_switch: 'Profile switching',
  test_model_reload: 'Model reload',
  test_invalid_language: 'Invalid language',
  test_invalid_voice: 'Invalid voice',
  test_empty_text: 'Empty text',
  test_oversized_input: 'Oversized input',
  test_concurrent: 'Concurrent requests',
  test_queue_overload: 'Queue overload',
  test_gpu_metrics: 'GPU metrics',
  test_openai_compat: 'OpenAI compatibility',
}

export function SelfTest() {
  const [result, setResult] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setBusy(true); setError(null); setResult(null)
    try {
      setResult(await api('/api/selftest', { method: 'POST' }))
    } catch (e: any) {
      setError(e.message)
    }
    setBusy(false)
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-2xl font-bold">Full Self Test</h1>
      <p className="text-sm text-zinc-400">
        Executes the complete 24-check suite: health, ready, models, voices, all formats,
        HTTP + WebSocket streaming, cancellation, profile switching, error handling,
        concurrency and OpenAI compatibility.
      </p>
      <button className="btn-primary" onClick={run} disabled={busy}>
        {busy ? 'Running…' : 'RUN FULL SELF TEST'}
      </button>
      {busy && <Spinner label="24 checks in progress (this takes a couple of minutes)" />}
      {error && <div className="text-sm text-red-400">{error}</div>}
      {result && (
        <Card title="Results">
          <div className="mb-4 text-lg font-semibold">
            {result.passed} / {result.total} PASSED
            {result.failed > 0 && <span className="text-red-400 ml-2">({result.failed} FAILED)</span>}
          </div>
          <table className="w-full text-sm">
            <tbody>
              {result.results.map((r: any) => (
                <tr key={r.name} className="border-t border-zinc-800">
                  <td className="py-1.5">{TEST_NAMES[r.name] || r.name}</td>
                  <td className="py-1.5">
                    {r.passed ? <Badge color="green">PASSED</Badge> : <Badge color="red">FAILED</Badge>}
                  </td>
                  <td className="py-1.5 text-xs text-zinc-500 max-w-md truncate" title={r.message}>{r.message}</td>
                  <td className="py-1.5 text-xs text-zinc-600 mono">{r.duration_ms.toFixed(0)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  )
}
