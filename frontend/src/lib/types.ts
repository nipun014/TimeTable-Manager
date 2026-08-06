/** The input schema the CP-SAT engine consumes. This type is the contract. */

export interface Subject {
  name: string
  hours_per_week: number
  room_type: string
  block_size: number
  is_heavy: boolean
}

export interface Teacher {
  name: string
  department: string
  can_teach: string[]
  /** Exactly days x periods_per_day. 1 = free, 0 = blocked. */
  availability: number[][]
}

export interface Room {
  type: string
  capacity: number
}

export interface Break {
  /** -1 means every day, otherwise a 0-based day index. */
  day: number
  period: number
  duration: number
  name: string
}

export interface Dataset {
  institution: { name: string; scheme: string; breaks: Break[] }
  days: number
  periods_per_day: number
  classes: string[]
  class_subjects: Record<string, string[]>
  subjects: Record<string, Subject>
  teachers: Record<string, Teacher>
  rooms: Record<string, Room>
  weights: Record<string, number>
  max_consecutive_periods: number
  early_periods: number[]
  late_periods: number[]
  solver_config: { max_time_seconds: number; num_workers: number; random_seed: number }
}

export const WEIGHT_LABELS: Record<string, string> = {
  teacher_unavailable: 'Respect teacher availability',
  teacher_idle_transition: 'Avoid gaps in teacher days',
  class_consecutive_overrun: 'Limit consecutive periods',
  subject_spread_excess: 'Spread subjects across the week',
  heavy_back_to_back: 'Avoid heavy subjects back to back',
  teacher_early_late_imbalance: 'Balance early and late slots',
}

export const DEFAULT_WEIGHTS: Record<string, number> = {
  teacher_unavailable: 10,
  teacher_idle_transition: 3,
  class_consecutive_overrun: 4,
  subject_spread_excess: 3,
  heavy_back_to_back: 2,
  teacher_early_late_imbalance: 2,
}

export const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
export const dayLabel = (i: number) => DAY_NAMES[i] ?? `Day ${i + 1}`

export function grid(days: number, periods: number, fill = 1): number[][] {
  return Array.from({ length: days }, () => Array<number>(periods).fill(fill))
}

/** Force a matrix to exactly days x periods. Mirrors `_reshape` in data_loader.py. */
export function reshape(rows: number[][] | undefined, days: number, periods: number): number[][] {
  const out: number[][] = (rows ?? []).slice(0, days).map((r) => {
    const row = r.slice(0, periods)
    while (row.length < periods) row.push(1)
    return row.map((v) => (v ? 1 : 0))
  })
  while (out.length < days) out.push(Array<number>(periods).fill(1))
  return out
}

/**
 * Fill in every optional field once, on load. Sample files omit plenty
 * (`block_size`, `is_heavy`, `class_subjects`), and pushing those defaults to
 * the edges means the whole builder can assume a complete object.
 */
export function normalize(raw: Record<string, unknown>): Dataset {
  const d = raw as Partial<Dataset> & Record<string, any>
  const days = Number(d.days) || 5
  const periods = Number(d.periods_per_day) || 6
  const classes: string[] = Array.isArray(d.classes) ? d.classes.map(String) : []
  const subjectKeys = Object.keys(d.subjects ?? {})

  const subjects: Record<string, Subject> = {}
  for (const [code, s] of Object.entries(d.subjects ?? {})) {
    const raw_s = s as any
    subjects[code] = {
      name: String(raw_s.name ?? ''),
      hours_per_week: Number(raw_s.hours_per_week) || 0,
      room_type: String(raw_s.room_type ?? 'standard'),
      // is_double_period is the legacy spelling of block_size: 2
      block_size: Number(raw_s.block_size) || (raw_s.is_double_period ? 2 : 1),
      is_heavy: Boolean(raw_s.is_heavy),
    }
  }

  const teachers: Record<string, Teacher> = {}
  for (const [id, t] of Object.entries(d.teachers ?? {})) {
    const raw_t = t as any
    teachers[id] = {
      name: String(raw_t.name ?? ''),
      department: String(raw_t.department ?? ''),
      can_teach: (raw_t.can_teach ?? []).map(String),
      availability: reshape(raw_t.availability, days, periods),
    }
  }

  const rooms: Record<string, Room> = {}
  for (const [id, r] of Object.entries(d.rooms ?? {})) {
    const raw_r = r as any
    rooms[id] = { type: String(raw_r.type ?? 'standard'), capacity: Number(raw_r.capacity) || 0 }
  }

  // never leave this to the backend default of "every class takes every subject" —
  // that turns an unfilled field into a guaranteed infeasibility
  const class_subjects: Record<string, string[]> = {}
  for (const c of classes) {
    const listed = d.class_subjects?.[c]
    class_subjects[c] = Array.isArray(listed) ? listed.filter((s) => s in subjects) : [...subjectKeys]
  }

  return {
    institution: {
      name: String(d.institution?.name ?? ''),
      scheme: String(d.institution?.scheme ?? ''),
      breaks: (d.institution?.breaks ?? []).map((b: any) => ({
        day: Number(b.day ?? -1),
        period: Number(b.period) || 0,
        duration: Number(b.duration) || 1,
        name: String(b.name ?? 'Break'),
      })),
    },
    days,
    periods_per_day: periods,
    classes,
    class_subjects,
    subjects,
    teachers,
    rooms,
    weights: { ...DEFAULT_WEIGHTS, ...(d.weights ?? {}) },
    max_consecutive_periods: Number(d.max_consecutive_periods) || 3,
    early_periods: d.early_periods ?? [0, 1],
    late_periods: d.late_periods ?? [periods - 2, periods - 1],
    solver_config: {
      max_time_seconds: Number(d.solver_config?.max_time_seconds) || 60,
      num_workers: Number(d.solver_config?.num_workers) || 8,
      random_seed: Number(d.solver_config?.random_seed ?? 42),
    },
  }
}

// ------------------------------------------------------------ solver output

export interface Slot {
  day: number
  period: number
  subject: string | null
  teacher?: string | null
  room?: string | null
  class?: string | null
}

export interface Solution {
  metadata: { timestamp: string; objective_value: number; days: number; periods_per_day: number }
  class_timetables: Record<string, Slot[][]>
  teacher_timetables: Record<string, Slot[][]>
  room_utilization: Record<string, Slot[][]>
}

export interface SolveResult {
  status: string
  solution?: Solution
  objective?: number
  runtime?: number
  violations?: string[]
  warnings?: string[]
  errors?: string[]
}
