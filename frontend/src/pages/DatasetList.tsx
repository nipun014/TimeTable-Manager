import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../lib/api'
import type { DatasetSummary, SampleInfo } from '../lib/api'

export default function DatasetList() {
  const nav = useNavigate()
  const [items, setItems] = useState<DatasetSummary[] | null>(null)
  const [samples, setSamples] = useState<SampleInfo[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const reload = () => api.listDatasets().then(setItems).catch(() => setItems([]))
  useEffect(() => {
    reload()
    api.samples().then(setSamples).catch(() => {})
  }, [])

  const create = async (body: { name?: string; sample?: string; data?: unknown }) => {
    setBusy(true)
    setError('')
    try {
      const made = await api.createDataset(body)
      nav(`/d/${made.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the timetable')
      setBusy(false)
    }
  }

  const uploadJson = async (file: File) => {
    try {
      const data = JSON.parse(await file.text())
      await create({ name: file.name.replace(/\.json$/i, ''), data })
    } catch (err) {
      setError(err instanceof SyntaxError ? `${file.name} is not valid JSON` : String(err))
    }
  }

  const remove = async (id: number, name: string) => {
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
    await api.deleteDataset(id)
    reload()
  }

  return (
    <main className="page">
      <div className="hero">
        <h1>Your timetables</h1>
        <p>Build the inputs, solve, and export. Nothing to install for whoever uses it.</p>
      </div>

      {error && (
        <div className="banner error" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div className="row wrap" style={{ marginBottom: '1.5rem' }}>
        <button className="primary" disabled={busy} onClick={() => create({})}>
          + New timetable
        </button>
        <button disabled={busy} onClick={() => fileRef.current?.click()}>
          Upload JSON
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".json,application/json"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            e.target.value = ''
            if (f) uploadJson(f)
          }}
        />
        <div className="spacer" />
        {samples.length > 0 && (
          <select
            style={{ width: 'auto' }}
            defaultValue=""
            disabled={busy}
            onChange={(e) => {
              if (e.target.value) create({ sample: e.target.value })
            }}
          >
            <option value="">Start from a sample…</option>
            {samples.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label} — {s.classes} classes, {s.teachers} teachers
              </option>
            ))}
          </select>
        )}
      </div>

      {items === null ? (
        <p className="dim">Loading…</p>
      ) : items.length === 0 ? (
        <div className="empty">
          <p>No timetables yet.</p>
          <p style={{ marginTop: '.4rem' }}>
            Start blank, or load a sample to see what a filled-in dataset looks like.
          </p>
        </div>
      ) : (
        <div className="dscards">
          {items.map((d) => (
            <div key={d.id} className="dscard">
              <Link to={`/d/${d.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                <div className="name">{d.name}</div>
                <div className="dim" style={{ marginTop: '.3rem' }}>
                  {d.counts.classes} classes · {d.counts.teachers} teachers ·{' '}
                  {d.counts.subjects} subjects · {d.counts.rooms} rooms
                </div>
              </Link>
              <div className="spacer" />
              <div className="row">
                <span className="dim">
                  {d.has_solution ? '✓ solved' : 'not solved yet'}
                </span>
                <div className="spacer" />
                {d.has_solution && (
                  <Link className="chip" to={`/d/${d.id}/result`} style={{ textDecoration: 'none' }}>
                    Result
                  </Link>
                )}
                <button className="ghost sm danger" onClick={() => remove(d.id, d.name)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  )
}
