import type { ReactNode } from 'react'

export function Card({ title, children, className = '' }: { title?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-zinc-800 bg-zinc-900/60 ${className}`}>
      {title && <div className="px-4 py-2 border-b border-zinc-800 text-sm font-semibold text-zinc-300">{title}</div>}
      <div className="p-4">{children}</div>
    </div>
  )
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-3">
      <div className="text-xs uppercase tracking-wide text-zinc-500">{label}</div>
      <div className="mt-1 text-xl font-semibold mono">{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-0.5">{sub}</div>}
    </div>
  )
}

export function Badge({ color, children }: { color?: string; children: ReactNode }) {
  const colors: Record<string, string> = {
    green: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    red: 'bg-red-500/15 text-red-400 border-red-500/30',
    amber: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    zinc: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
    blue: 'bg-sky-500/15 text-sky-400 border-sky-500/30',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${colors[color || 'zinc']}`}>
      {children}
    </span>
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-zinc-400">
      <div className="h-4 w-4 border-2 border-zinc-600 border-t-sky-400 rounded-full animate-spin" />
      {label}
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="block text-xs uppercase tracking-wide text-zinc-500 mb-1">{label}</span>
      {children}
      {hint && <span className="block text-[11px] text-zinc-600 mt-0.5">{hint}</span>}
    </label>
  )
}

export const btnCls = 'btn'
