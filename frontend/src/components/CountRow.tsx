import { useEffect, useRef, useState } from 'react'

interface Props {
  label: string
  count: number
  onApply: (n: number) => void
  onAdd: () => void
  /** Names that would be dropped by shrinking to n — shown in the confirm dialog. */
  dropping: (n: number) => string[]
  addLabel?: string
}

/**
 * The number box is a *target*, not a binding to `count`.
 *
 * It re-syncs from `count` whenever that changes — but only while the input is
 * not focused. That one condition is what stops "set the count to 18" and the
 * individual +/Remove buttons from fighting: the buttons keep the box current,
 * and typing `18` is never stomped between the `1` and the `8`.
 */
export default function CountRow({ label, count, onApply, onAdd, dropping, addLabel }: Props) {
  const [draft, setDraft] = useState(String(count))
  const inputRef = useRef<HTMLInputElement>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const [pending, setPending] = useState<{ n: number; names: string[] } | null>(null)

  useEffect(() => {
    if (document.activeElement !== inputRef.current) setDraft(String(count))
  }, [count])

  const apply = () => {
    const n = Number(draft)
    if (!Number.isFinite(n) || n < 0) {
      setDraft(String(count))
      return
    }
    const target = Math.min(Math.floor(n), 200)
    if (target === count) return
    // growing is harmless; shrinking throws away filled-in work, so it asks first
    if (target < count) {
      setPending({ n: target, names: dropping(target) })
      dialogRef.current?.showModal()
      return
    }
    onApply(target)
  }

  return (
    <div className="countrow">
      <div className="field">
        <label htmlFor={`count-${label}`}>{label}</label>
        <input
          id={`count-${label}`}
          ref={inputRef}
          type="number"
          min={0}
          max={200}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={apply}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              apply()
              inputRef.current?.blur()
            }
            if (e.key === 'Escape') setDraft(String(count))
          }}
        />
      </div>
      <button onClick={apply} disabled={Number(draft) === count}>
        Apply
      </button>
      <button onClick={onAdd}>{addLabel ?? '+ Add one'}</button>
      <div className="spacer" />
      <span className="dim">
        {count} {count === 1 ? 'entry' : 'entries'}
      </span>

      <dialog
        ref={dialogRef}
        onClose={() => {
          setPending(null)
          setDraft(String(count))
        }}
      >
        <h3>Remove {count - (pending?.n ?? 0)} of {count}?</h3>
        <p className="muted" style={{ margin: '.6rem 0' }}>
          These will be deleted along with everything filled in on them:
        </p>
        <div className="chips" style={{ maxHeight: 180, overflowY: 'auto' }}>
          {pending?.names.map((n) => (
            <span key={n} className="chip static">
              {n}
            </span>
          ))}
        </div>
        <div className="row" style={{ marginTop: '1.1rem' }}>
          <div className="spacer" />
          <button onClick={() => dialogRef.current?.close()}>Cancel</button>
          <button
            className="primary danger"
            onClick={() => {
              if (pending) onApply(pending.n)
              dialogRef.current?.close()
            }}
          >
            Remove them
          </button>
        </div>
      </dialog>
    </div>
  )
}
