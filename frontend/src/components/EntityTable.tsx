export interface Column {
  key: string
  label: string
  type: 'text' | 'number' | 'select' | 'bool'
  options?: string[]
  /** select columns that also accept a typed-in value */
  freeText?: boolean
  min?: number
  max?: number
  placeholder?: string
  width?: string
  title?: string
}

interface Props {
  ids: string[]
  idLabel: string
  columns: Column[]
  values: (id: string) => Record<string, unknown>
  onRename: (id: string, to: string) => void
  onPatch: (id: string, patch: Record<string, unknown>) => void
  onRemove: (id: string) => void
  highlight?: Set<string>
  emptyHint: string
}

const ADD_NEW = '__add__'

/** One table serves subjects, rooms and classes — three descriptor arrays instead
 *  of three near-identical components. */
export default function EntityTable({
  ids,
  idLabel,
  columns,
  values,
  onRename,
  onPatch,
  onRemove,
  highlight,
  emptyHint,
}: Props) {
  if (ids.length === 0) return <div className="empty">{emptyHint}</div>

  return (
    <div className="scroll-x">
      <table className="etable">
        <thead>
          <tr>
            <th style={{ width: '150px' }}>{idLabel}</th>
            {columns.map((c) => (
              <th key={c.key} style={{ width: c.width }} title={c.title}>
                {c.label}
              </th>
            ))}
            <th className="shrink" />
          </tr>
        </thead>
        <tbody>
          {ids.map((id) => {
            const v = values(id)
            const bad = highlight?.has(id)
            return (
              <tr key={id}>
                <td>
                  <input
                    defaultValue={id}
                    key={id}
                    style={bad ? { borderColor: 'var(--bad)' } : undefined}
                    onBlur={(e) => onRename(id, e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                  />
                </td>
                {columns.map((c) => (
                  <td key={c.key} className={c.type === 'number' ? 'num' : undefined}>
                    {c.type === 'bool' ? (
                      <input
                        type="checkbox"
                        checked={Boolean(v[c.key])}
                        onChange={(e) => onPatch(id, { [c.key]: e.target.checked })}
                      />
                    ) : c.type === 'select' ? (
                      <select
                        value={String(v[c.key] ?? '')}
                        onChange={(e) => {
                          if (c.freeText && e.target.value === ADD_NEW) {
                            const typed = prompt(`New ${c.label.toLowerCase()}:`)?.trim()
                            if (typed) onPatch(id, { [c.key]: typed })
                            return
                          }
                          onPatch(id, { [c.key]: e.target.value })
                        }}
                      >
                        {!c.options?.includes(String(v[c.key])) && (
                          <option value={String(v[c.key] ?? '')}>{String(v[c.key] ?? '')}</option>
                        )}
                        {c.options?.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                        {c.freeText && <option value={ADD_NEW}>+ new type…</option>}
                      </select>
                    ) : (
                      <input
                        type={c.type}
                        min={c.min}
                        max={c.max}
                        placeholder={c.placeholder}
                        value={String(v[c.key] ?? '')}
                        onChange={(e) =>
                          onPatch(id, {
                            [c.key]: c.type === 'number' ? Number(e.target.value) : e.target.value,
                          })
                        }
                      />
                    )}
                  </td>
                ))}
                <td className="shrink">
                  <button
                    className="ghost sm danger"
                    aria-label={`Remove ${id}`}
                    onClick={() => onRemove(id)}
                  >
                    ✕
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
