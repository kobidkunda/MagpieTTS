import { useEffect, useState } from 'react'
import { api, type SystemInfo } from './api'
import { Dashboard } from './pages/Dashboard'
import { Playground } from './pages/Playground'
import { RealtimeLab } from './pages/RealtimeLab'
import { Voices } from './pages/Voices'
import { Pronunciation } from './pages/Pronunciation'
import { Models } from './pages/Models'
import { Performance } from './pages/Performance'
import { ApiTester } from './pages/ApiTester'
import { SelfTest } from './pages/SelfTest'
import { Logs } from './pages/Logs'
import { SystemPage } from './pages/SystemPage'
import { RealtimeDocs } from './pages/RealtimeDocs'

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: '▦' },
  { id: 'playground', label: 'Playground', icon: '◉' },
  { id: 'realtime', label: 'Realtime Lab', icon: '⇄' },
  { id: 'voices', label: 'Voices', icon: '♬' },
  { id: 'pronunciation', label: 'Pronunciation', icon: 'Aa' },
  { id: 'models', label: 'Models', icon: '◇' },
  { id: 'performance', label: 'Performance', icon: '∿' },
  { id: 'apitest', label: 'API Tester', icon: '⧉' },
  { id: 'selftest', label: 'Self Test', icon: '✓' },
  { id: 'realtimedocs', label: 'Realtime Docs', icon: '≋' },
  { id: 'logs', label: 'Logs', icon: '≡' },
  { id: 'system', label: 'System', icon: '⚙' },
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [sys, setSys] = useState<SystemInfo | null>(null)
  const [ws, setWs] = useState(false)

  useEffect(() => {
    const poll = async () => {
      try {
        const s = await api<SystemInfo>('/api/system')
        setSys(s)
        setWs(true)
      } catch {
        setWs(false)
      }
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [])

  const ready = sys?.model?.state === 'active'

  return (
    <div className="flex h-screen">
      <aside className="w-56 border-r border-zinc-800 bg-zinc-950 flex flex-col shrink-0">
        <div className="px-4 py-4 border-b border-zinc-800">
          <div className="font-bold text-lg tracking-tight">Magpie TTS</div>
          <div className="mt-1 flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${ready ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
            <span className="text-xs text-zinc-500">{ready ? 'Ready' : ws ? 'Loading model' : 'Offline'}</span>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map((n) => (
            <button
              key={n.id}
              onClick={() => setPage(n.id)}
              className={`w-full text-left px-4 py-2 text-sm flex items-center gap-3 transition-colors ${
                page === n.id ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
              }`}
            >
              <span className="w-5 text-center text-xs opacity-70">{n.icon}</span>
              {n.label}
            </button>
          ))}
          <a href="/docs" target="_blank" className="block px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 flex items-center gap-3">
            <span className="w-5 text-center text-xs opacity-70">⎘</span>Swagger /docs
          </a>
          <a href="/redoc" target="_blank" className="block px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 flex items-center gap-3">
            <span className="w-5 text-center text-xs opacity-70">⎘</span>ReDoc /redoc
          </a>
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-12 border-b border-zinc-800 flex items-center px-4 gap-6 text-xs text-zinc-400">
          <span className="font-medium text-zinc-300">MODEL: {sys?.model?.revision || '—'}</span>
          <span>PROFILE: {(sys?.model?.profile || '—').toUpperCase()}</span>
          <span>GPU: {sys?.gpu?.device || 'cuda:0'}</span>
          <span>
            VRAM: {sys?.gpu?.used_mb ?? '—'} / {sys?.gpu?.total_mb ?? '—'} MB
          </span>
          <span>SESSIONS: {sys?.runtime?.active_sessions ? 1 : 0}</span>
          <span className="ml-auto">v{sys?.server?.version || '—'}</span>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          {page === 'dashboard' && <Dashboard sys={sys} onNav={setPage} />}
          {page === 'playground' && <Playground />}
          {page === 'realtime' && <RealtimeLab />}
          {page === 'voices' && <Voices />}
          {page === 'pronunciation' && <Pronunciation />}
          {page === 'models' && <Models />}
          {page === 'performance' && <Performance />}
          {page === 'apitest' && <ApiTester />}
          {page === 'selftest' && <SelfTest />}
          {page === 'realtimedocs' && <RealtimeDocs />}
          {page === 'logs' && <Logs />}
          {page === 'system' && <SystemPage sys={sys} />}
        </main>
      </div>
    </div>
  )
}
