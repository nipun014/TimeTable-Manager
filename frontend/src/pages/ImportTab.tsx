import { useRef, useState } from 'react'
import { api, ApiError } from '../lib/api'
import type { ParsedSheet } from '../lib/api'
import type { Action } from '../lib/builderReducer'
import { FIELDS, applyImport, guessMapping } from '../lib/import'
import type { SheetMapping, Target } from '../lib/import'
import type { Dataset } from '../lib/types'

const TARGETS: { value: Target; label: string }[] = [
  { value: 'skip', label: "Don't import" },
  { value: 'classes', label: 'Classes' },
  { value: 'subjects', label: 'Subjects' },
  { value: 'teachers', label: 'Teachers' },
  { value: 'rooms', label: 'Rooms' },
]

export default function ImportTab({ data, edit }: { data: Dataset; edit: (a: Action) => void }) {
  const [sheets, setSheets] = useState<ParsedSheet[] | null>(null)
  const [mapping, setMapping] = useState<Record<string, SheetMapping>>({})
  const [error, setError] = useState('')
  const [done, setDone] = useState<string[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = async (file: File) => {
    setBusy(true)
    setError('')
    setDone(null)
    try {
      const res = await api.parseSheet(file)
      setSheets(res.sheets)
      setMapping(Object.fromEntries(res.sheets.map((s) => [s.name, guessMapping(s)])))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Could not read that file')
      setSheets(null)
    } finally {
      setBusy(false)
    }
  }

  const merge = () => {
    if (!sheets) return
    const { data: next, summary } = applyImport(data, sheets, mapping)
    edit({ type: 'replace', data: next })
    setDone(summary.length ? summary : ['Nothing was imported — no sheet is mapped to an entity.'])
  }

  const active = sheets?.filter((s) => mapping[s.name]?.target !== 'skip') ?? []

  return (
    <div className="stack">
      <div className="card stack">
        <div className="row wrap">
          <h3>Import from a spreadsheet</h3>
          <div className="spacer" />
          <a className="chip" href="/api/import/template" style={{ textDecoration: 'none', padding: '.45rem .8rem' }}>
            ⬇ Download the template
          </a>
        </div>
        <p className="dim">
          Upload any .xlsx or .csv — one sheet per entity, or several files one after
          another. You tell it which column means what; nothing is imported until you
          press Merge, and nothing already in the builder is deleted.
        </p>

        <div
          className="empty"
          style={dragging ? { borderColor: 'var(--accent)', color: 'var(--text)' } : undefined}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            const f = e.dataTransfer.files?.[0]
            if (f) load(f)
          }}
        >
          {busy ? (
            <p>
              <span className="spin" /> Reading…
            </p>
          ) : (
            <>
              <p>Drop a spreadsheet here</p>
              <p style={{ marginTop: '.5rem' }}>
                <button onClick={() => fileRef.current?.click()}>Choose a file</button>
              </p>
            </>
          )}
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,.csv,.txt"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0]
              e.target.value = ''
              if (f) load(f)
            }}
          />
        </div>

        {error && <div className="banner error">{error}</div>}
      </div>

      {done && (
        <div className="banner info">
          <b>Imported.</b>
          <ul style={{ margin: '.4rem 0 0', paddingLeft: '1.1rem' }}>
            {done.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {sheets?.map((sheet) => {
        const map = mapping[sheet.name]
        const set = (patch: Partial<SheetMapping>) =>
          setMapping({ ...mapping, [sheet.name]: { ...map, ...patch } })

        return (
          <details key={sheet.name} className="tcard" open={map.target !== 'skip'}>
            <summary>
              <b>{sheet.name}</b>
              <span className="dim">
                {sheet.rows.length} rows · {sheet.headers.length} columns
              </span>
              <div className="spacer" />
              <select
                style={{ width: 'auto' }}
                value={map.target}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => {
                  const target = e.target.value as Target
                  set(target === 'skip' ? { target } : { ...guessMapping(sheet), target })
                }}
              >
                {TARGETS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </summary>

            {map.target !== 'skip' && (
              <div className="body" style={{ gridTemplateColumns: '1fr' }}>
                <div className="grid2">
                  {FIELDS[map.target].map((f) => (
                    <div key={f.key}>
                      <label>
                        {f.label}
                        {f.required && <span style={{ color: 'var(--bad)' }}> *</span>}
                      </label>
                      <select
                        value={map.fields[f.key] ?? -1}
                        onChange={(e) =>
                          set({ fields: { ...map.fields, [f.key]: Number(e.target.value) } })
                        }
                      >
                        <option value={-1}>— not in this sheet —</option>
                        {sheet.headers.map((h, i) => (
                          <option key={i} value={i}>
                            {h}
                          </option>
                        ))}
                      </select>
                      {f.hint && <p className="dim" style={{ marginTop: '.25rem' }}>{f.hint}</p>}
                    </div>
                  ))}
                </div>

                <div className="scroll-x" style={{ marginTop: '.5rem' }}>
                  <table className="etable">
                    <thead>
                      <tr>
                        {sheet.headers.map((h, i) => {
                          const mapped = Object.entries(map.fields).find(([, col]) => col === i)
                          return (
                            <th key={i}>
                              {h}
                              {mapped && (
                                <div style={{ color: 'var(--accent-soft)', fontWeight: 500 }}>
                                  → {FIELDS[map.target as Exclude<Target, 'skip'>].find((f) => f.key === mapped[0])?.label}
                                </div>
                              )}
                            </th>
                          )
                        })}
                      </tr>
                    </thead>
                    <tbody>
                      {sheet.rows.slice(0, 5).map((row, i) => (
                        <tr key={i}>
                          {sheet.headers.map((_, j) => (
                            <td key={j} style={{ padding: '.3rem .5rem' }}>
                              {row[j] === null || row[j] === undefined ? '' : String(row[j])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {sheet.rows.length > 5 && (
                    <p className="dim" style={{ marginTop: '.4rem' }}>
                      Previewing 5 of {sheet.rows.length} rows.
                    </p>
                  )}
                </div>
              </div>
            )}
          </details>
        )
      })}

      {sheets && (
        <div className="row">
          <button className="primary" onClick={merge} disabled={active.length === 0}>
            Merge {active.length} sheet{active.length === 1 ? '' : 's'} into this timetable
          </button>
          <button onClick={() => { setSheets(null); setDone(null) }}>Cancel</button>
          <div className="spacer" />
          <span className="dim">Existing entries are updated, never deleted.</span>
        </div>
      )}
    </div>
  )
}
