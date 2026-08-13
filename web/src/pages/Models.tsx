import { useEffect, useState } from 'react'
import { api, switchProfile } from '../api'
import { Card, Badge, Spinner } from '../components/ui'

interface Profile { id: string; name: string; precision: string; description: string; status: string; loadable: boolean; measured_vram_mb: number | null; last_load_ms: number | null }

export function Models() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [current, setCurrent] = useState<string | null>(null)
  const [state, setState] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [log, setLog] = useState<string[]>([])

  const load = async () => {
    try {
      const r = await api<any>('/api/profiles')
      setProfiles(r.data)
      setCurrent(r.current)
      setState(r.state)
    } catch { /* offline */ }
  }
  useEffect(() => { load(); const id = setInterval(load, 4000); return () => clearInterval(id) }, [])

  const switchTo = async (id: string) => {
    setBusy(true)
    try {
      const r = await switchProfile(id)
      setLog((l) => [...l.slice(-40), `→ ${id}: ${JSON.stringify(r.model?.state)}`])
      await load()
    } catch (e: any) {
      setLog((l) => [...l.slice(-40), `✗ ${id}: ${e.message}`])
    }
    setBusy(false)
  }

  const precisionBadge = (p: string) =>
    p === 'int8' || p === 'int4'
      ? <Badge color="red">experimental</Badge>
      : p === 'fp16' ? <Badge color="green">{p}</Badge> : <Badge color="blue">{p}</Badge>

  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">Model / Precision Manager</h1>
      {state === 'switching' && <Spinner label="model is switching profiles…" />}
      <Card title="Profiles">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-zinc-500">
              <th className="pb-2">Profile</th><th className="pb-2">Precision</th>
              <th className="pb-2">Status</th><th className="pb-2">VRAM (measured)</th>
              <th className="pb-2">Load time</th><th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr key={p.id} className="border-t border-zinc-800">
                <td className="py-2 font-medium">{p.name}</td>
                <td className="py-2">{precisionBadge(p.precision)}</td>
                <td className="py-2">
                  {current === p.id ? <Badge color="green">ACTIVE</Badge>
                    : p.status === 'missing' ? <Badge color="red">MISSING</Badge>
                    : <Badge>{p.status.toUpperCase()}</Badge>}
                </td>
                <td className="py-2 mono">{p.measured_vram_mb != null ? `${p.measured_vram_mb} MB` : '—'}</td>
                <td className="py-2 mono">{p.last_load_ms != null ? `${p.last_load_ms.toFixed(0)} ms` : '—'}</td>
                <td className="py-2 text-right">
                  {current === p.id ? (
                    <span className="text-xs text-zinc-500">Active</span>
                  ) : p.loadable ? (
                    <button className="btn text-xs" onClick={() => switchTo(p.id)} disabled={busy || state === 'switching'}>
                      Load
                    </button>
                  ) : (
                    <button className="btn text-xs opacity-60" disabled title={p.description}>Setup</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-3 text-xs text-zinc-500">
          INT8/INT4 remain unavailable until a validated conversion/runtime is installed. Never guessed VRAM — only measured values are shown.
        </p>
      </Card>
      <Card title="Switch history">
        <div className="mono text-xs space-y-1 h-40 overflow-y-auto">
          {log.length === 0 && <div className="text-zinc-600">No switches yet.</div>}
          {log.map((l, i) => <div key={i}>{l}</div>)}
        </div>
      </Card>
    </div>
  )
}
