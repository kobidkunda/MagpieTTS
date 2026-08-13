import type { SystemInfo } from '../api'
import { Card, Stat, Badge } from '../components/ui'

export function SystemPage({ sys }: { sys: SystemInfo | null }) {
  return (
    <div className="space-y-6 max-w-6xl">
      <h1 className="text-2xl font-bold">System</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Status" value={<Badge color={sys?.status === 'ready' ? 'green' : 'amber'}>{sys?.status || 'offline'}</Badge>} />
        <Stat label="Server" value={sys?.server?.name || '—'} sub={`v${sys?.server?.version || '—'}`} />
        <Stat label="GPU" value={sys?.gpu?.device || '—'} sub={`${sys?.gpu?.power_w ?? '—'} W`} />
        <Stat label="GPU util" value={`${sys?.gpu?.utilization ?? '—'}%`} sub={`${sys?.gpu?.temperature ?? '—'} °C`} />
      </div>
      <Card title="Full /api/system payload">
        <pre className="mono text-xs text-zinc-400 overflow-x-auto">{JSON.stringify(sys, null, 2)}</pre>
      </Card>
    </div>
  )
}
