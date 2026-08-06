import { hueFor } from '../lib/colors'
import type { Slot } from '../lib/types'
import { dayLabel } from '../lib/types'

interface Props {
  table: Slot[][]
  /** Which slot field is the headline, and which fill the subtitle. */
  titleKey: keyof Slot
  subKeys: (keyof Slot)[]
}

export default function TimetableGrid({ table, titleKey, subKeys }: Props) {
  const periods = table[0]?.length ?? 0
  return (
    <div className="scroll-x">
      <table className="tt">
        <thead>
          <tr>
            <th className="day" />
            {Array.from({ length: periods }, (_, p) => (
              <th key={p}>P{p + 1}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.map((day, d) => (
            <tr key={d}>
              <th className="day">{dayLabel(d)}</th>
              {day.map((slot, p) => {
                const title = slot[titleKey]
                if (!title)
                  return (
                    <td key={p}>
                      <div className="cell free">
                        <b>Free</b>
                      </div>
                    </td>
                  )
                const h = hueFor(String(title))
                const sub = subKeys
                  .map((k) => slot[k])
                  .filter(Boolean)
                  .join(' · ')
                return (
                  <td key={p}>
                    <div
                      className="cell"
                      style={{
                        background: `hsl(${h} 55% 16%)`,
                        border: `1px solid hsl(${h} 55% 30%)`,
                      }}
                    >
                      <b style={{ color: `hsl(${h} 80% 78%)` }}>{String(title)}</b>
                      <span>{sub}</span>
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
