import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'

export function AudioPlayer({ src, name, onEnded }: { src: string; name?: string; onEnded?: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WaveSurfer | null>(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    if (!src || !containerRef.current) return
    const ws = WaveSurfer.create({
      container: containerRef.current,
      height: 48,
      waveColor: '#3f3f46',
      progressColor: '#818cf8',
      cursorColor: '#a1a1aa',
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
    })
    ws.load(src)
    ws.on('finish', () => { setPlaying(false); onEnded?.() })
    ws.on('play', () => setPlaying(true))
    ws.on('pause', () => setPlaying(false))
    wsRef.current = ws
    return () => { ws.destroy(); wsRef.current = null }
  }, [src])

  const toggle = () => { wsRef.current?.[playing ? 'pause' : 'play']() }
  const stop = () => { wsRef.current?.stop(); setPlaying(false) }

  return (
    <div className="flex items-center gap-2">
      <button onClick={toggle} className="btn-primary h-9 w-9 flex items-center justify-center">
        {playing ? '❚❚' : '▶'}
      </button>
      <button onClick={stop} className="btn h-9 w-9 flex items-center justify-center" title="Stop">
        ■
      </button>
      <div ref={containerRef} className="flex-1 min-w-0" />
      {name && (
        <a href={src} download={name} className="btn h-9 flex items-center px-2" title="Download">
          ⬇
        </a>
      )}
    </div>
  )
}
