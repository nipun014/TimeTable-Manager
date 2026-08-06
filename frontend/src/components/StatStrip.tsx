export interface Stat {
  value: string | number
  label: string
  tone?: 'ok' | 'warn' | 'bad'
}

export default function StatStrip({ stats }: { stats: Stat[] }) {
  return (
    <div className="stats">
      {stats.map((s) => (
        <div key={s.label} className={`stat ${s.tone ?? ''}`}>
          <div className="v">{s.value}</div>
          <div className="k">{s.label}</div>
        </div>
      ))}
    </div>
  )
}
