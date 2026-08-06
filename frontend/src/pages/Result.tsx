import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import StatStrip from '../components/StatStrip'
import TimetableGrid from '../components/TimetableGrid'
import { api, ApiError } from '../lib/api'
import type { Slot, SolveResult } from '../lib/types'
import { dayLabel, normalize } from '../lib/types'

type View = 'classes' | 'teachers' | 'rooms' | 'export'

const VIEWS: Record<Exclude<View, 'export'>, { title: string; titleKey: keyof Slot; subKeys: (keyof Slot)[] }> = {
  classes: { title: 'Class', titleKey: 'subject', subKeys: ['teacher', 'room'] },
  teachers: { title: 'Teacher', titleKey: 'subject', subKeys: ['class', 'room'] },
  rooms: { title: 'Room', titleKey: 'subject', subKeys: ['class', 'teacher'] },
}

export default function Result() {
  const { id } = useParams()
  const datasetId = Number(id)
  const nav = useNavigate()
  const location = useLocation() as { state?: { autoSolve?: boolean } }

  const [name, setName] = useState('')
  const [result, setResult] = useState<SolveResult | null>(null)
  const [settings, setSettings] = useState({ time_limit: 60, seed: 42 })
  const [solving, setSolving] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [error, setError] = useState('')
  const [view, setView] = useState<View>('classes')
  const [pick, setPick] = useState('')
  const started = useRef(false)

  const solve = useCallback(
    async (time_limit: number, seed: number) => {
      setSolving(true)
      setError('')
      setElapsed(0)
      const tick = setInterval(() => setElapsed((e) => e + 1), 1000)
      try {
        setResult(await api.solve(datasetId, time_limit, seed))
      } catch (e) {
        setError(e instanceof ApiError ? e.message : 'The solve request failed')
      } finally {
        clearInterval(tick)
        setSolving(false)
      }
    },
    [datasetId],
  )

  useEffect(() => {
    api
      .getDataset(datasetId)
      .then((d) => {
        setName(d.name)
        const cfg = normalize(d.data).solver_config
        const next = { time_limit: cfg.max_time_seconds, seed: cfg.random_seed }
        setSettings(next)
        if (location.state?.autoSolve && !started.current) {
          started.current = true
          solve(next.time_limit, next.seed)
        } else {
          setResult(d.last_solution)
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Could not load this timetable'))
  }, [datasetId, location.state, solve])

  const solution = result?.solution
  const tables =
    solution && view !== 'export'
      ? view === 'classes'
        ? solution.class_timetables
        : view === 'teachers'
          ? solution.teacher_timetables
          : solution.room_utilization
      : null
  const options = tables ? Object.keys(tables) : []
  const active = tables && (pick in tables ? pick : options[0])

  const rows = solution
    ? Object.entries(solution.class_timetables).flatMap(([cls, table]) =>
        table.flatMap((day, d) =>
          day.map((s) => [
            cls,
            dayLabel(d),
            `P${s.period}`,
            s.subject ?? 'Free',
            s.teacher ?? '-',
            s.room ?? '-',
          ]),
        ),
      )
    : []

  const downloadCsv = () => {
    const cell = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v)
    const csv = [['Class', 'Day', 'Period', 'Subject', 'Teacher', 'Room'], ...rows]
      .map((r) => r.map(cell).join(','))
      .join('\n')
    download(new Blob([csv], { type: 'text/csv' }), `${name || 'timetable'}.csv`)
  }

  const downloadJson = () =>
    download(
      new Blob([JSON.stringify(solution, null, 2)], { type: 'application/json' }),
      `${name || 'timetable'}-solution.json`,
    )

  const free = solution
    ? Object.values(solution.class_timetables)
        .flat(2)
        .filter((s) => !s.subject).length
    : 0

  return (
    <main className="page">
      <div className="row wrap" style={{ marginBottom: '1.25rem' }}>
        <div>
          <h1>{name}</h1>
          <p className="muted">Generated timetable</p>
        </div>
        <div className="spacer" />
        <button onClick={() => nav(`/d/${datasetId}`)}>← Edit inputs</button>
        <div className="row" style={{ gap: '.4rem' }}>
          <input
            type="number"
            min={5}
            max={180}
            style={{ width: 78 }}
            aria-label="Time limit in seconds"
            value={settings.time_limit}
            onChange={(e) => setSettings({ ...settings, time_limit: Number(e.target.value) })}
          />
          <span className="dim">s</span>
          <input
            type="number"
            style={{ width: 78 }}
            aria-label="Random seed"
            value={settings.seed}
            onChange={(e) => setSettings({ ...settings, seed: Number(e.target.value) })}
          />
        </div>
        <button className="primary" disabled={solving} onClick={() => solve(settings.time_limit, settings.seed)}>
          {solving ? <><span className="spin" /> Solving… {elapsed}s</> : result ? '⚡ Solve again' : '⚡ Generate'}
        </button>
      </div>

      {error && <div className="banner error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {solving && (
        <div className="banner info" style={{ marginBottom: '1rem' }}>
          Searching for a timetable — up to {settings.time_limit}s. It usually finishes much sooner.
        </div>
      )}

      {(result?.warnings ?? []).map((w, i) => (
        <div key={i} className="banner warn" style={{ marginBottom: '.5rem' }}>
          {w.replace(/^\[WARN\]\s*/, '')}
        </div>
      ))}

      {!result && !solving && !error && (
        <div className="empty">
          Not solved yet. Press Generate to run the solver.
        </div>
      )}

      {result && !solution && (
        <div className="stack">
          <div className="banner error">
            {result.status === 'UNKNOWN'
              ? `Ran out of time after ${settings.time_limit}s without finding a valid timetable. It is not proven impossible — try a longer time limit or a different seed.`
              : result.status === 'INVALID'
                ? 'The inputs cannot produce a timetable. Fix these, then try again:'
                : `No timetable found — solver status: ${result.status}`}
          </div>
          {(result.errors ?? []).map((e, i) => (
            <div key={i} className="banner error">
              {e.replace(/^[⚠️\s]*\[?(ERROR|WARN)\]?\s*/, '')}
            </div>
          ))}
          <div>
            <button onClick={() => nav(`/d/${datasetId}`)}>← Back to the inputs</button>
          </div>
        </div>
      )}

      {solution && (
        <>
          <StatStrip
            stats={[
              { value: result.status === 'OPTIMAL' ? 'Optimal' : 'Feasible', label: 'Status', tone: 'ok' },
              {
                value: result.violations?.length ?? 0,
                label: 'Violations',
                tone: result.violations?.length ? 'bad' : 'ok',
              },
              { value: Math.round(result.objective ?? 0), label: 'Penalty score', tone: result.objective ? 'warn' : 'ok' },
              { value: free, label: 'Free slots' },
              { value: `${(result.runtime ?? 0).toFixed(1)}s`, label: 'Solve time' },
            ]}
          />

          {(result.violations?.length ?? 0) > 0 && (
            <details className="issues" open>
              <summary>
                <span className="badge error">{result.violations!.length} violations</span>
                <span className="muted">The solution breaks hard constraints — this is a bug, please report it.</span>
              </summary>
              {result.violations!.slice(0, 25).map((v, i) => (
                <div key={i} className="issue">{v}</div>
              ))}
            </details>
          )}

          <nav className="tabs" role="tablist">
            {(['classes', 'teachers', 'rooms', 'export'] as View[]).map((v) => (
              <button
                key={v}
                role="tab"
                aria-selected={view === v}
                onClick={() => {
                  setView(v)
                  setPick('')
                }}
              >
                {v[0].toUpperCase() + v.slice(1)}
              </button>
            ))}
          </nav>

          {view !== 'export' && tables && (
            <div className="stack">
              <div className="row">
                <select
                  style={{ width: 'auto', minWidth: 220 }}
                  aria-label={VIEWS[view].title}
                  value={active ?? ''}
                  onChange={(e) => setPick(e.target.value)}
                >
                  {options.map((o) => (
                    <option key={o} value={o}>
                      {o}
                    </option>
                  ))}
                </select>
                <span className="dim">{VIEWS[view].title} timetable</span>
              </div>
              {active && (
                <TimetableGrid
                  table={tables[active]}
                  titleKey={VIEWS[view].titleKey}
                  subKeys={VIEWS[view].subKeys}
                />
              )}
            </div>
          )}

          {view === 'export' && (
            <div className="stack">
              <div className="row wrap">
                <button onClick={downloadCsv}>⬇ CSV</button>
                <button onClick={downloadJson}>⬇ Solution JSON</button>
                <a className="chip" href={`/api/datasets/${datasetId}/solution.xlsx`} style={{ textDecoration: 'none', padding: '.5rem .9rem' }}>
                  ⬇ Excel
                </a>
                <div className="spacer" />
                <span className="dim">{rows.length} rows</span>
              </div>
              <div className="scroll-x card" style={{ maxHeight: 480, overflowY: 'auto', padding: '.5rem' }}>
                <table className="etable">
                  <thead>
                    <tr>
                      {['Class', 'Day', 'Period', 'Subject', 'Teacher', 'Room'].map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.slice(0, 400).map((r, i) => (
                      <tr key={i}>
                        {r.map((c, j) => (
                          <td key={j} style={{ padding: '.3rem .5rem' }}>
                            {c}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {rows.length > 400 && (
                  <p className="dim" style={{ padding: '.6rem' }}>
                    Showing the first 400 rows — the download has all {rows.length}.
                  </p>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </main>
  )
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
