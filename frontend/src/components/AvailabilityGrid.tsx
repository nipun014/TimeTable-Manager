import { useEffect, useRef } from 'react'
import { dayLabel } from '../lib/types'

interface Props {
  value: number[][]
  onChange: (next: number[][]) => void
}

/** Days × periods toggle grid with drag painting. Green = the teacher is free. */
export default function AvailabilityGrid({ value, onChange }: Props) {
  const days = value.length
  const periods = value[0]?.length ?? 0
  // what a drag is painting (1 or 0), decided by the cell the drag started on
  const paint = useRef<number | null>(null)

  useEffect(() => {
    const stop = () => (paint.current = null)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    return () => {
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
    }
  }, [])

  const set = (d: number, p: number, v: number) => {
    if (value[d][p] === v) return
    onChange(value.map((row, i) => (i === d ? row.map((c, j) => (j === p ? v : c)) : row)))
  }

  const setRow = (d: number) => {
    const v = value[d].every((c) => c === 1) ? 0 : 1
    onChange(value.map((row, i) => (i === d ? row.map(() => v) : row)))
  }

  const setCol = (p: number) => {
    const v = value.every((row) => row[p] === 1) ? 0 : 1
    onChange(value.map((row) => row.map((c, j) => (j === p ? v : c))))
  }

  const setAll = () => {
    const v = value.every((row) => row.every((c) => c === 1)) ? 0 : 1
    onChange(value.map((row) => row.map(() => v)))
  }

  return (
    <div
      className="avgrid"
      style={{ gridTemplateColumns: `auto repeat(${periods}, minmax(34px, 1fr))` }}
    >
      <button className="hdr day" onClick={setAll} title="Toggle every slot">
        ⇱
      </button>
      {Array.from({ length: periods }, (_, p) => (
        <button key={p} className="hdr" onClick={() => setCol(p)} title={`Toggle period ${p + 1}`}>
          P{p + 1}
        </button>
      ))}

      {Array.from({ length: days }, (_, d) => (
        <div key={d} style={{ display: 'contents' }}>
          <button className="hdr day" onClick={() => setRow(d)} title={`Toggle ${dayLabel(d)}`}>
            {dayLabel(d)}
          </button>
          {Array.from({ length: periods }, (_, p) => (
            <button
              key={p}
              className="cell"
              role="checkbox"
              aria-checked={value[d][p] === 1}
              aria-label={`${dayLabel(d)} period ${p + 1}`}
              onPointerDown={(e) => {
                e.preventDefault()
                paint.current = value[d][p] === 1 ? 0 : 1
                set(d, p, paint.current)
              }}
              onPointerEnter={() => {
                if (paint.current !== null) set(d, p, paint.current)
              }}
              onKeyDown={(e) => {
                if (e.key === ' ' || e.key === 'Enter') {
                  e.preventDefault()
                  set(d, p, value[d][p] === 1 ? 0 : 1)
                }
              }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
