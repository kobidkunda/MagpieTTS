import { useEffect, useState } from 'react'
import { api } from '../api'
import { Card } from '../components/ui'

export function Logs() {
  const [lines, setLines] = useState<string[]>([])
  const [auto, setAuto] = useState(true)

  const load = () => api<{ lines: string[] }>('/api/logs?lines=300').then((r) => setLines(r.lines)).catch(() => {})

  useEffect(() => {
    load()
    let id: ReturnType<typeof setInterval> | null = null
    if (auto) {
      id = setInterval(load, 3000)
    }
    return () => { if (id) clearInterval(id) }
  }, [auto])

  return (
    <div className="space-y-4 max-w-6xl">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">Logs / Diagnostics</h1>
        <label className="flex items-center gap-1.5 text-sm text-zinc-400">
          <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="h-4 w-4 accent-indigo-500" />
          auto-refresh
        </label>
        <button className="btn" onClick={load}>Refresh</button>
      </div>
      <Card>
        <pre className="mono text-[11px] text-zinc-300 overflow-x-auto h-[70vh] overflow-y-auto whitespace-pre-wrap">
          {lines.join('\n')}
        </pre>
      </Card>
    </div>
  )
}
