import type { SystemInfo } from '../api'
import { Card, Stat, Badge } from '../components/ui'

export function Dashboard({ sys, onNav }: { sys: SystemInfo | null; onNav: (p: string) => void }) {
  const stats = sys?.stats
  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Server" value={<Badge color={sys ? 'green' : 'red'}>{sys ? 'READY' : 'OFFLINE'}</Badge>} />
        <Stat label="Model" value={sys?.model?.model_id || '—'} sub={`revision ${sys?.model?.revision || '—'}`} />
        <Stat label="Profile" value={(sys?.model?.profile || '—').toUpperCase()} sub={`precision ${sys?.model?.precision || '—'}`} />
        <Stat label="Device" value={sys?.gpu?.device || 'cuda:0'} />
        <Stat label="GPU memory" value={`${sys?.gpu?.used_mb ?? '—'} MB`} sub={`free ${sys?.gpu?.free_mb ?? '—'} MB`} />
        <Stat label="GPU util" value={`${sys?.gpu?.utilization ?? '—'}%`} sub={`temp ${sys?.gpu?.temperature ?? '—'}°C`} />
        <Stat label="Queue" value={sys?.runtime?.queue ?? '—'} sub={`active ${sys?.runtime?.active_sessions ? 1 : 0}`} />
        <Stat label="Requests" value={stats?.requests ?? 0} sub={`errors ${stats?.errors ?? 0} · cancelled ${stats?.cancelled ?? 0}`} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Last TTFA" value={`${(stats?.ttfa?.last ?? 0).toFixed(0)} ms`} />
        <Stat label="P50 TTFA" value={`${(stats?.ttfa?.p50 ?? 0).toFixed(0)} ms`} />
        <Stat label="P95 TTFA" value={`${(stats?.ttfa?.p95 ?? 0).toFixed(0)} ms`} />
        <Stat label="RTF (p50)" value={(stats?.rtf?.p50 ?? 0).toFixed(3)} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <button className="btn h-20 flex flex-col items-center justify-center gap-1" onClick={() => onNav('playground')}>
          <span className="text-lg">◉</span> TTS Playground
        </button>
        <button className="btn h-20 flex flex-col items-center justify-center gap-1" onClick={() => onNav('realtime')}>
          <span className="text-lg">⇄</span> Realtime Lab
        </button>
        <button className="btn h-20 flex flex-col items-center justify-center gap-1" onClick={() => onNav('selftest')}>
          <span className="text-lg">✓</span> Self Test
        </button>
        <button className="btn h-20 flex flex-col items-center justify-center gap-1" onClick={() => onNav('performance')}>
          <span className="text-lg">∿</span> Benchmark
        </button>
      </div>
      <Card title="Model state">
        <pre className="mono text-xs text-zinc-400 overflow-x-auto">{JSON.stringify(sys?.model ?? {}, null, 2)}</pre>
      </Card>
    </div>
  )
}
