// API helpers for the Magpie TTS server GUI.

const BASE = ''

export interface SystemInfo {
  status: string
  server: { version: string; name: string }
  model: any
  gpu: any
  runtime: any
  stats: any
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  })
  if (!res.ok) {
    let body: any = null
    try { body = await res.json() } catch { /* noop */ }
    const msg = body?.error?.message || `${res.status} ${res.statusText}`
    throw new ApiError(msg, res.status, body?.error)
  }
  if (res.status === 204) return undefined as T
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return (await res.arrayBuffer()) as unknown as T
}

export class ApiError extends Error {
  status: number
  code?: string
  constructor(message: string, status: number, body?: any) {
    super(message)
    this.status = status
    this.code = body?.code
  }
}

export async function synthesize(params: {
  text: string
  language: string
  voice: string
  format: string
  speed?: number
  sampleRate?: number
  tn?: boolean
  cfg?: boolean
  cfgScale?: number
}): Promise<{ blob: Blob; url: string; headers: Headers }> {
  const res = await fetch(`${BASE}/v1/audio/speech`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'magpie-tts-multilingual-357m',
      input: params.text,
      voice: params.voice,
      language: params.language,
      response_format: params.format,
      speed: params.speed ?? 1.0,
      sample_rate: params.sampleRate,
      text_normalization: params.tn ?? true,
      cfg_enabled: params.cfg ?? false,
      cfg_scale: params.cfgScale ?? 2.5,
    }),
  })
  if (!res.ok) {
    let body: any = null
    try { body = await res.json() } catch { /* noop */ }
    throw new ApiError(body?.error?.message || res.statusText, res.status, body?.error)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  return { blob, url, headers: res.headers }
}

export async function switchProfile(profile: string): Promise<any> {
  return api('/api/profiles/switch', {
    method: 'POST',
    body: JSON.stringify({ profile }),
  })
}

export async function runSelftest(): Promise<any> {
  return api('/api/selftest', { method: 'POST' })
}

export async function runBenchmark(req: any): Promise<any> {
  return api('/api/benchmark', { method: 'POST', body: JSON.stringify(req) })
}

export const wsUrl = (path: string) => {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}${BASE}${path}`
}
