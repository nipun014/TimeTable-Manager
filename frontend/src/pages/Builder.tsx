import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import AvailabilityGrid from '../components/AvailabilityGrid'
import CountRow from '../components/CountRow'
import EntityTable from '../components/EntityTable'
import type { Column } from '../components/EntityTable'
import StatStrip from '../components/StatStrip'
import ImportTab from './ImportTab'
import { api, ApiError } from '../lib/api'
import { reducer } from '../lib/builderReducer'
import type { Action } from '../lib/builderReducer'
import type { Dataset } from '../lib/types'
import { WEIGHT_LABELS, dayLabel, normalize } from '../lib/types'
import { blockedSlots, validate } from '../lib/validate'
import type { Issue } from '../lib/validate'

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

const TABS = [
  ['setup', 'Setup'],
  ['classes', 'Classes'],
  ['subjects', 'Subjects'],
  ['teachers', 'Teachers'],
  ['rooms', 'Rooms'],
  ['constraints', 'Constraints'],
  ['import', 'Import'],
  ['json', 'JSON'],
] as const
type TabKey = (typeof TABS)[number][0]

function rootReducer(state: Dataset | null, action: Action): Dataset | null {
  if (action.type === 'replace') return action.data
  return state ? reducer(state, action) : state
}

export default function Builder() {
  const { id } = useParams()
  const datasetId = Number(id)
  const nav = useNavigate()

  const [data, dispatch] = useReducer(rootReducer, null)
  const [name, setName] = useState('')
  const [tab, setTab] = useState<TabKey>('setup')
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [loadError, setLoadError] = useState('')
  const [focusId, setFocusId] = useState<string | null>(null)
  const dirty = useRef(false)
  const latest = useRef<{ data: Dataset; name: string } | null>(null)

  /** Every user edit goes through here so autosave knows the state is dirty. */
  const edit = useCallback((action: Action) => {
    dirty.current = true
    dispatch(action)
  }, [])

  useEffect(() => {
    api
      .getDataset(datasetId)
      .then((d) => {
        setName(d.name)
        dispatch({ type: 'replace', data: normalize(d.data) })
      })
      .catch((e) => setLoadError(e instanceof ApiError ? e.message : 'Could not load this timetable'))
  }, [datasetId])

  useEffect(() => {
    if (data) latest.current = { data, name }
  }, [data, name])

  // debounced autosave. PUT returns 204 with no body, so a slow response can
  // never overwrite newer local edits.
  useEffect(() => {
    if (!data || !dirty.current) return
    setSaveState('saving')
    const t = setTimeout(() => {
      api
        .saveDataset(datasetId, { data, name })
        .then(() => setSaveState('saved'))
        .catch(() => setSaveState('error'))
    }, 800)
    return () => clearTimeout(t)
  }, [data, name, datasetId])

  // leaving the page must not drop the last few hundred milliseconds of edits
  useEffect(
    () => () => {
      if (dirty.current && latest.current)
        api.saveDataset(datasetId, latest.current).catch(() => {})
    },
    [datasetId],
  )

  const issues = useMemo(() => (data ? validate(data) : []), [data])
  const errorCount = issues.filter((i) => i.level === 'error').length

  const flushThenSolve = async () => {
    if (!data) return
    setSaveState('saving')
    try {
      await api.saveDataset(datasetId, { data, name })
      dirty.current = false
      setSaveState('saved')
    } catch {
      setSaveState('error')
      return
    }
    nav(`/d/${datasetId}/result`, { state: { autoSolve: true } })
  }

  if (loadError) return <main className="page"><div className="banner error">{loadError}</div></main>
  if (!data) return <main className="page dim">Loading…</main>

  const roomTypes = [...new Set(Object.values(data.rooms).map((r) => r.type))].sort()
  const subjectIds = Object.keys(data.subjects)
  const teacherIds = Object.keys(data.teachers)
  const slotsPerClass = data.days * data.periods_per_day - blockedSlots(data)

  const jump = (issue: Issue) => {
    setTab(issue.tab as TabKey)
    setFocusId(issue.id ?? null)
  }

  return (
    <main className="page">
      <div className="row wrap" style={{ marginBottom: '1.25rem', gap: '.9rem' }}>
        <div style={{ flex: '1 1 260px' }}>
          <input
            value={name}
            aria-label="Timetable name"
            onChange={(e) => {
              dirty.current = true
              setName(e.target.value)
            }}
            style={{ fontSize: '1.4rem', fontWeight: 620, border: 0, background: 'transparent', padding: '.2rem 0' }}
          />
          <div className={`savedot ${saveState === 'saving' ? '' : saveState}`}>
            {saveState === 'saving' ? 'Saving…' : saveState === 'error' ? 'Could not save' : saveState === 'saved' ? 'All changes saved' : 'Loaded'}
          </div>
        </div>
        <button onClick={() => nav('/')}>← All timetables</button>
        <button onClick={() => nav(`/d/${datasetId}/result`)}>Last result</button>
        <button className="primary" onClick={flushThenSolve} disabled={errorCount > 0}>
          ⚡ Generate timetable
        </button>
      </div>

      <StatStrip
        stats={[
          { value: data.classes.length, label: 'Classes' },
          { value: teacherIds.length, label: 'Teachers' },
          { value: subjectIds.length, label: 'Subjects' },
          { value: Object.keys(data.rooms).length, label: 'Rooms' },
          { value: `${data.days}×${data.periods_per_day}`, label: 'Slots / week' },
          {
            value: issues.length === 0 ? 'Ready' : `${errorCount} / ${issues.length - errorCount}`,
            label: issues.length === 0 ? 'Status' : 'Errors / warnings',
            tone: errorCount ? 'bad' : issues.length ? 'warn' : 'ok',
          },
        ]}
      />

      {issues.length > 0 && (
        <details className="issues" open={errorCount > 0}>
          <summary>
            <span className={`badge ${errorCount ? 'error' : 'warn'}`}>
              {errorCount ? `${errorCount} error${errorCount > 1 ? 's' : ''}` : 'check'}
            </span>
            <span className="muted">
              {errorCount
                ? 'Fix these before generating — the solver cannot succeed as-is.'
                : `${issues.length} thing${issues.length > 1 ? 's' : ''} worth a look.`}
            </span>
          </summary>
          {issues.map((issue, i) => (
            <button key={i} className="issue" onClick={() => jump(issue)}>
              <span className={`badge ${issue.level === 'error' ? 'error' : 'warn'}`}>
                {issue.level}
              </span>
              <span>{issue.message}</span>
            </button>
          ))}
        </details>
      )}

      <nav className="tabs" role="tablist">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => {
              setTab(key)
              setFocusId(null)
            }}
          >
            {label}
            {key === 'classes' && <span className="count">{data.classes.length}</span>}
            {key === 'subjects' && <span className="count">{subjectIds.length}</span>}
            {key === 'teachers' && <span className="count">{teacherIds.length}</span>}
            {key === 'rooms' && <span className="count">{Object.keys(data.rooms).length}</span>}
          </button>
        ))}
      </nav>

      {tab === 'setup' && <SetupTab data={data} edit={edit} slotsPerClass={slotsPerClass} />}

      {tab === 'classes' && (
        <>
          <CountRow
            label="Classes"
            count={data.classes.length}
            onApply={(n) => edit({ type: 'setCount', kind: 'classes', n })}
            onAdd={() => edit({ type: 'add', kind: 'classes' })}
            dropping={(n) => data.classes.slice(n)}
            addLabel="+ Add class"
          />
          {data.classes.length === 0 ? (
            <div className="empty">
              No classes yet. Set a count above — say 6 — and they appear ready to rename.
            </div>
          ) : (
            <div className="stack">
              {data.classes.map((c) => (
                <div key={c} className="card" style={focusId === c ? { borderColor: 'var(--bad)' } : undefined}>
                  <div className="row wrap" style={{ marginBottom: '.75rem' }}>
                    <input
                      key={c}
                      defaultValue={c}
                      aria-label="Class name"
                      style={{ maxWidth: 220, fontWeight: 600 }}
                      onBlur={(e) => edit({ type: 'rename', kind: 'classes', id: c, to: e.target.value })}
                      onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                    />
                    <span className="dim">
                      {(data.class_subjects[c] ?? []).reduce(
                        (n, s) => n + (data.subjects[s]?.hours_per_week ?? 0),
                        0,
                      )}{' '}
                      of {slotsPerClass} slots used
                    </span>
                    <div className="spacer" />
                    <button
                      className="sm"
                      onClick={() => edit({ type: 'setClassSubjects', cls: c, subjects: [...subjectIds] })}
                    >
                      Select all
                    </button>
                    <button
                      className="sm"
                      onClick={() => edit({ type: 'setClassSubjects', cls: c, subjects: [] })}
                    >
                      Clear
                    </button>
                    <button className="ghost sm danger" onClick={() => edit({ type: 'remove', kind: 'classes', id: c })}>
                      ✕
                    </button>
                  </div>
                  {subjectIds.length === 0 ? (
                    <p className="dim">Add subjects first, then tick the ones this class takes.</p>
                  ) : (
                    <div className="chips">
                      {subjectIds.map((s) => (
                        <button
                          key={s}
                          className="chip"
                          aria-pressed={(data.class_subjects[c] ?? []).includes(s)}
                          onClick={() => edit({ type: 'toggleClassSubject', cls: c, subject: s })}
                        >
                          {s}
                          <span className="dim"> · {data.subjects[s].hours_per_week}h</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'subjects' && (
        <>
          <CountRow
            label="Subjects"
            count={subjectIds.length}
            onApply={(n) => edit({ type: 'setCount', kind: 'subjects', n })}
            onAdd={() => edit({ type: 'add', kind: 'subjects' })}
            dropping={(n) => subjectIds.slice(n)}
            addLabel="+ Add subject"
          />
          <EntityTable
            ids={subjectIds}
            idLabel="Code"
            emptyHint="No subjects yet. Set a count above, or add them one at a time."
            highlight={focusId ? new Set([focusId]) : undefined}
            columns={subjectColumns(roomTypes)}
            values={(s) => data.subjects[s] as unknown as Record<string, unknown>}
            onRename={(from, to) => edit({ type: 'rename', kind: 'subjects', id: from, to })}
            onPatch={(sid, patch) => edit({ type: 'patch', kind: 'subjects', id: sid, patch })}
            onRemove={(sid) => edit({ type: 'remove', kind: 'subjects', id: sid })}
          />
          <p className="dim" style={{ marginTop: '.9rem' }}>
            <b>Block size</b> is how many periods in a row one session runs — 3 for a KTU lab,
            1 for a normal lecture. Weekly hours must divide evenly by it.
          </p>
        </>
      )}

      {tab === 'teachers' && (
        <>
          <CountRow
            label="Teachers"
            count={teacherIds.length}
            onApply={(n) => edit({ type: 'setCount', kind: 'teachers', n })}
            onAdd={() => edit({ type: 'add', kind: 'teachers' })}
            dropping={(n) => teacherIds.slice(n)}
            addLabel="+ Add teacher"
          />
          {teacherIds.length === 0 ? (
            <div className="empty">
              No teachers yet. Type how many you have above and press Apply.
            </div>
          ) : (
            teacherIds.map((t) => (
              <details key={t} className="tcard" open={focusId === t}>
                <summary>
                  <b>{t}</b>
                  <span className="dim">{data.teachers[t].name || 'unnamed'}</span>
                  <div className="spacer" />
                  <span className="dim">
                    {data.teachers[t].can_teach.length} subject
                    {data.teachers[t].can_teach.length === 1 ? '' : 's'} ·{' '}
                    {data.teachers[t].availability.flat().reduce((a, b) => a + b, 0)} free slots
                  </span>
                </summary>
                <div className="body">
                  <div className="stack">
                    <div className="grid2">
                      <div>
                        <label>Teacher ID</label>
                        <input
                          key={t}
                          defaultValue={t}
                          onBlur={(e) => edit({ type: 'rename', kind: 'teachers', id: t, to: e.target.value })}
                          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                        />
                      </div>
                      <div>
                        <label>Name</label>
                        <input
                          value={data.teachers[t].name}
                          placeholder="Dr. Anitha R"
                          onChange={(e) => edit({ type: 'patch', kind: 'teachers', id: t, patch: { name: e.target.value } })}
                        />
                      </div>
                      <div>
                        <label>Department</label>
                        <input
                          value={data.teachers[t].department}
                          placeholder="Mathematics"
                          onChange={(e) => edit({ type: 'patch', kind: 'teachers', id: t, patch: { department: e.target.value } })}
                        />
                      </div>
                    </div>
                    <div>
                      <label>Can teach</label>
                      {subjectIds.length === 0 ? (
                        <p className="dim">Add subjects first.</p>
                      ) : (
                        <div className="chips">
                          {subjectIds.map((s) => (
                            <button
                              key={s}
                              className="chip"
                              aria-pressed={data.teachers[t].can_teach.includes(s)}
                              onClick={() => edit({ type: 'toggleCanTeach', teacher: t, subject: s })}
                            >
                              {s}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                    <button
                      className="ghost sm danger"
                      style={{ alignSelf: 'flex-start' }}
                      onClick={() => edit({ type: 'remove', kind: 'teachers', id: t })}
                    >
                      Remove this teacher
                    </button>
                  </div>

                  <div className="stack" style={{ gap: '.6rem' }}>
                    <div className="row">
                      <label style={{ margin: 0 }}>Availability</label>
                      <div className="spacer" />
                      {teacherIds.length > 1 && (
                        <select
                          style={{ width: 'auto', fontSize: '.82rem' }}
                          value=""
                          onChange={(e) =>
                            e.target.value && edit({ type: 'copyAvailability', from: e.target.value, to: t })
                          }
                        >
                          <option value="">Copy from…</option>
                          {teacherIds.filter((o) => o !== t).map((o) => (
                            <option key={o} value={o}>
                              {o}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                    <AvailabilityGrid
                      value={data.teachers[t].availability}
                      onChange={(availability) => edit({ type: 'setAvailability', teacher: t, availability })}
                    />
                    <p className="dim">
                      Filled = free to teach. Click and drag to paint; click a day or period
                      header to flip the whole row or column.
                    </p>
                  </div>
                </div>
              </details>
            ))
          )}
        </>
      )}

      {tab === 'rooms' && (
        <>
          <CountRow
            label="Rooms"
            count={Object.keys(data.rooms).length}
            onApply={(n) => edit({ type: 'setCount', kind: 'rooms', n })}
            onAdd={() => edit({ type: 'add', kind: 'rooms' })}
            dropping={(n) => Object.keys(data.rooms).slice(n)}
            addLabel="+ Add room"
          />
          <EntityTable
            ids={Object.keys(data.rooms)}
            idLabel="Room ID"
            emptyHint="No rooms yet. You need at least as many rooms as classes."
            highlight={focusId ? new Set([focusId]) : undefined}
            columns={[
              {
                key: 'type',
                label: 'Type',
                type: 'select',
                freeText: true,
                options: [...new Set([...roomTypes, 'standard', 'lab', 'computer_lab', 'electronics_lab'])].sort(),
                title: 'Subjects are matched to rooms by this exact string',
              },
              { key: 'capacity', label: 'Capacity', type: 'number', min: 0, width: '110px' },
            ]}
            values={(r) => data.rooms[r] as unknown as Record<string, unknown>}
            onRename={(from, to) => edit({ type: 'rename', kind: 'rooms', id: from, to })}
            onPatch={(rid, patch) => edit({ type: 'patch', kind: 'rooms', id: rid, patch })}
            onRemove={(rid) => edit({ type: 'remove', kind: 'rooms', id: rid })}
          />
          <p className="dim" style={{ marginTop: '.9rem' }}>
            Room <b>type</b> is what subjects match against. Capacity is recorded but not
            yet constrained by the solver.
          </p>
        </>
      )}

      {tab === 'constraints' && <ConstraintsTab data={data} edit={edit} />}

      {tab === 'import' && <ImportTab data={data} edit={edit} />}

      {tab === 'json' && <JsonTab data={data} name={name} edit={edit} />}
    </main>
  )
}

function subjectColumns(roomTypes: string[]): Column[] {
  return [
    { key: 'name', label: 'Name', type: 'text', placeholder: 'Discrete Mathematics' },
    { key: 'hours_per_week', label: 'Hrs / week', type: 'number', min: 0, max: 40, width: '110px' },
    {
      key: 'room_type',
      label: 'Room type',
      type: 'select',
      freeText: true,
      width: '160px',
      options: [...new Set([...roomTypes, 'standard'])].sort(),
      title: 'Must match the type of at least one room',
    },
    { key: 'block_size', label: 'Block', type: 'number', min: 1, max: 8, width: '90px', title: 'Consecutive periods per session' },
    { key: 'is_heavy', label: 'Heavy', type: 'bool', width: '70px', title: 'Heavy subjects are spread apart where possible' },
  ]
}

// ---------------------------------------------------------------- setup tab

function SetupTab({
  data,
  edit,
  slotsPerClass,
}: {
  data: Dataset
  edit: (a: Action) => void
  slotsPerClass: number
}) {
  return (
    <div className="stack">
      <div className="card stack">
        <h3>Institution</h3>
        <div className="grid2">
          <div>
            <label>Name</label>
            <input
              value={data.institution.name}
              placeholder="Model Engineering College"
              onChange={(e) => edit({ type: 'setInstitution', patch: { name: e.target.value } })}
            />
          </div>
          <div>
            <label>Scheme</label>
            <input
              value={data.institution.scheme}
              placeholder="KTU 2019"
              onChange={(e) => edit({ type: 'setInstitution', patch: { scheme: e.target.value } })}
            />
          </div>
        </div>
      </div>

      <div className="card stack">
        <h3>The week</h3>
        <div className="grid2">
          <div>
            <label>Working days ({dayLabel(0)}–{dayLabel(data.days - 1)})</label>
            <input
              type="number"
              min={1}
              max={7}
              value={data.days}
              onChange={(e) => edit({ type: 'setDims', days: Number(e.target.value) })}
            />
          </div>
          <div>
            <label>Periods per day</label>
            <input
              type="number"
              min={1}
              max={12}
              value={data.periods_per_day}
              onChange={(e) => edit({ type: 'setDims', periods: Number(e.target.value) })}
            />
          </div>
        </div>
        <p className="dim">
          {data.days * data.periods_per_day} slots a week, {slotsPerClass} teachable after
          breaks. Changing these reshapes every teacher's availability grid to match.
        </p>
      </div>

      <div className="card stack">
        <div className="row">
          <h3>Breaks</h3>
          <div className="spacer" />
          <button className="sm" onClick={() => edit({ type: 'addBreak' })}>
            + Add break
          </button>
        </div>
        {data.institution.breaks.length === 0 ? (
          <p className="dim">No breaks. Add one to keep a lunch period clear of classes.</p>
        ) : (
          <div className="scroll-x">
            <table className="etable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th style={{ width: 140 }}>Day</th>
                  <th style={{ width: 130 }}>Starts at</th>
                  <th style={{ width: 110 }}>Periods</th>
                  <th className="shrink" />
                </tr>
              </thead>
              <tbody>
                {data.institution.breaks.map((b, i) => (
                  <tr key={i}>
                    <td>
                      <input
                        value={b.name}
                        onChange={(e) => edit({ type: 'patchBreak', index: i, patch: { name: e.target.value } })}
                      />
                    </td>
                    <td>
                      <select
                        value={b.day}
                        onChange={(e) => edit({ type: 'patchBreak', index: i, patch: { day: Number(e.target.value) } })}
                      >
                        <option value={-1}>Every day</option>
                        {Array.from({ length: data.days }, (_, d) => (
                          <option key={d} value={d}>
                            {dayLabel(d)}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <select
                        value={b.period}
                        onChange={(e) => edit({ type: 'patchBreak', index: i, patch: { period: Number(e.target.value) } })}
                      >
                        {Array.from({ length: data.periods_per_day }, (_, p) => (
                          <option key={p} value={p}>
                            Period {p + 1}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="num">
                      <input
                        type="number"
                        min={1}
                        max={data.periods_per_day}
                        value={b.duration}
                        onChange={(e) => edit({ type: 'patchBreak', index: i, patch: { duration: Number(e.target.value) } })}
                      />
                    </td>
                    <td className="shrink">
                      <button className="ghost sm danger" onClick={() => edit({ type: 'removeBreak', index: i })}>
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------- constraints tab

function ConstraintsTab({ data, edit }: { data: Dataset; edit: (a: Action) => void }) {
  const periodPicker = (key: 'early_periods' | 'late_periods') => (
    <div className="chips">
      {Array.from({ length: data.periods_per_day }, (_, p) => (
        <button
          key={p}
          className="chip"
          aria-pressed={data[key].includes(p)}
          onClick={() =>
            edit({
              type: 'setPeriodList',
              key,
              value: data[key].includes(p) ? data[key].filter((x) => x !== p) : [...data[key], p],
            })
          }
        >
          P{p + 1}
        </button>
      ))}
    </div>
  )

  return (
    <div className="stack">
      <div className="card stack">
        <div>
          <h3>Soft rules</h3>
          <p className="dim" style={{ marginTop: '.3rem' }}>
            These never make a timetable impossible — they decide which of the valid ones
            the solver prefers. Higher means it tries harder.
          </p>
        </div>
        <div className="grid2">
          {Object.entries(WEIGHT_LABELS).map(([key, label]) => (
            <div key={key}>
              <label htmlFor={`w-${key}`}>
                {label} <span style={{ color: 'var(--dim)' }}>· {data.weights[key] ?? 0}</span>
              </label>
              <input
                id={`w-${key}`}
                type="range"
                min={0}
                max={20}
                value={data.weights[key] ?? 0}
                onChange={(e) => edit({ type: 'setWeight', key, value: Number(e.target.value) })}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="card stack">
        <h3>Shape of the day</h3>
        <div>
          <label htmlFor="maxcons">
            Max consecutive periods of one subject · {data.max_consecutive_periods}
          </label>
          <input
            id="maxcons"
            type="range"
            min={1}
            max={8}
            value={data.max_consecutive_periods}
            onChange={(e) => edit({ type: 'setMaxConsecutive', value: Number(e.target.value) })}
          />
        </div>
        <div>
          <label>Early periods</label>
          {periodPicker('early_periods')}
        </div>
        <div>
          <label>Late periods</label>
          {periodPicker('late_periods')}
        </div>
        <p className="dim">
          Used to balance who gets stuck with the first and last slots of the day.
        </p>
      </div>

      <div className="card stack">
        <h3>Solver</h3>
        <div className="grid2">
          <div>
            <label>Time limit (seconds)</label>
            <input
              type="number"
              min={5}
              max={180}
              value={data.solver_config.max_time_seconds}
              onChange={(e) => edit({ type: 'setSolverConfig', patch: { max_time_seconds: Number(e.target.value) } })}
            />
          </div>
          <div>
            <label>Random seed</label>
            <input
              type="number"
              value={data.solver_config.random_seed}
              onChange={(e) => edit({ type: 'setSolverConfig', patch: { random_seed: Number(e.target.value) } })}
            />
          </div>
          <div>
            <label>Search workers</label>
            <input
              type="number"
              min={1}
              max={16}
              value={data.solver_config.num_workers}
              onChange={(e) => edit({ type: 'setSolverConfig', patch: { num_workers: Number(e.target.value) } })}
            />
          </div>
        </div>
        <p className="dim">
          A different seed explores the search differently — worth a try when a hard dataset
          runs out of time.
        </p>
      </div>
    </div>
  )
}

// ----------------------------------------------------------------- json tab

function JsonTab({ data, name, edit }: { data: Dataset; name: string; edit: (a: Action) => void }) {
  const [draft, setDraft] = useState(() => JSON.stringify(data, null, 2))
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  // reflect edits made on the other tabs, but never clobber what is being typed
  useEffect(() => {
    if (document.activeElement?.tagName !== 'TEXTAREA') {
      setDraft(JSON.stringify(data, null, 2))
      setError('')
    }
  }, [data])

  const apply = (text: string) => {
    try {
      edit({ type: 'replace', data: normalize(JSON.parse(text)) })
      setError('')
    } catch (e) {
      setError(e instanceof SyntaxError ? `Not valid JSON — ${e.message}` : String(e))
    }
  }

  const download = () => {
    const url = URL.createObjectURL(new Blob([draft], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `${name || 'timetable'}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="stack">
      <div className="row wrap">
        <button className="primary" onClick={() => apply(draft)}>
          Apply changes
        </button>
        <button onClick={download}>⬇ Download JSON</button>
        <button onClick={() => fileRef.current?.click()}>⬆ Upload JSON</button>
        <input
          ref={fileRef}
          type="file"
          accept=".json,application/json"
          hidden
          onChange={async (e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
            if (f) apply(await f.text())
          }}
        />
        <div className="spacer" />
        <span className="dim">The exact payload sent to the solver.</span>
      </div>
      {error && <div className="banner error">{error}</div>}
      <textarea
        className="json"
        spellCheck={false}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
    </div>
  )
}
