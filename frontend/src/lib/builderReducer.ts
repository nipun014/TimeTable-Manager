/** All dataset mutation lives here. Pure function, so it is trivially checkable
 *  (see checks.ts) and deep-nested edits stay out of the components. */
import type { Break, Dataset, Room, Subject, Teacher } from './types'
import { grid, reshape } from './types'

export type EntityKind = 'subjects' | 'teachers' | 'rooms' | 'classes'

export type Action =
  | { type: 'replace'; data: Dataset }
  | { type: 'setDims'; days?: number; periods?: number }
  | { type: 'setInstitution'; patch: Partial<Dataset['institution']> }
  | { type: 'setWeight'; key: string; value: number }
  | { type: 'setMaxConsecutive'; value: number }
  | { type: 'setPeriodList'; key: 'early_periods' | 'late_periods'; value: number[] }
  | { type: 'setSolverConfig'; patch: Partial<Dataset['solver_config']> }
  | { type: 'setCount'; kind: EntityKind; n: number }
  | { type: 'add'; kind: EntityKind; id?: string }
  | { type: 'remove'; kind: EntityKind; id: string }
  | { type: 'rename'; kind: EntityKind; id: string; to: string }
  | { type: 'patch'; kind: 'subjects' | 'teachers' | 'rooms'; id: string; patch: Record<string, unknown> }
  | { type: 'toggleClassSubject'; cls: string; subject: string }
  | { type: 'setClassSubjects'; cls: string; subjects: string[] }
  | { type: 'toggleCanTeach'; teacher: string; subject: string }
  | { type: 'setAvailability'; teacher: string; availability: number[][] }
  | { type: 'copyAvailability'; from: string; to: string }
  | { type: 'addBreak' }
  | { type: 'patchBreak'; index: number; patch: Partial<Break> }
  | { type: 'removeBreak'; index: number }

const PREFIX: Record<EntityKind, string> = {
  subjects: 'SUB',
  teachers: 'T',
  rooms: 'R',
  classes: 'Class ',
}

export function idsOf(d: Dataset, kind: EntityKind): string[] {
  return kind === 'classes' ? d.classes : Object.keys(d[kind])
}

/** First unused `PREFIX + n` id, so growing a count never collides. */
export function nextId(taken: Set<string>, kind: EntityKind): string {
  const pad = kind === 'classes' ? 0 : 2
  for (let n = 1; ; n++) {
    const id = PREFIX[kind] + String(n).padStart(pad, '0')
    if (!taken.has(id)) return id
  }
}

function blank(kind: EntityKind, d: Dataset): Subject | Teacher | Room {
  if (kind === 'subjects')
    return { name: '', hours_per_week: 3, room_type: 'standard', block_size: 1, is_heavy: false }
  if (kind === 'teachers')
    return { name: '', department: '', can_teach: [], availability: grid(d.days, d.periods_per_day) }
  return { type: 'standard', capacity: 30 }
}

function withEntity(d: Dataset, kind: EntityKind, id: string): Dataset {
  if (kind === 'classes') {
    if (d.classes.includes(id)) return d
    return { ...d, classes: [...d.classes, id], class_subjects: { ...d.class_subjects, [id]: [] } }
  }
  if (id in d[kind]) return d
  return { ...d, [kind]: { ...d[kind], [id]: blank(kind, d) } }
}

function withoutEntity(d: Dataset, kind: EntityKind, id: string): Dataset {
  if (kind === 'classes') {
    const { [id]: _drop, ...class_subjects } = d.class_subjects
    return { ...d, classes: d.classes.filter((c) => c !== id), class_subjects }
  }
  const { [id]: _gone, ...rest } = d[kind] as Record<string, unknown>
  const next = { ...d, [kind]: rest } as Dataset
  if (kind !== 'subjects') return next
  // a deleted subject must stop being referenced, or the solver sees a phantom
  return {
    ...next,
    class_subjects: Object.fromEntries(
      Object.entries(next.class_subjects).map(([c, list]) => [c, list.filter((s) => s !== id)]),
    ),
    teachers: Object.fromEntries(
      Object.entries(next.teachers).map(([t, info]) => [
        t,
        { ...info, can_teach: info.can_teach.filter((s) => s !== id) },
      ]),
    ),
  }
}

function renamed(d: Dataset, kind: EntityKind, from: string, to: string): Dataset {
  to = to.trim()
  if (!to || to === from || idsOf(d, kind).includes(to)) return d

  if (kind === 'classes') {
    return {
      ...d,
      classes: d.classes.map((c) => (c === from ? to : c)),
      class_subjects: Object.fromEntries(
        Object.entries(d.class_subjects).map(([c, list]) => [c === from ? to : c, list]),
      ),
    }
  }

  // preserve insertion order: rebuild the record rather than delete-then-append
  const rebuilt = Object.fromEntries(
    Object.entries(d[kind] as Record<string, unknown>).map(([k, v]) => [k === from ? to : k, v]),
  )
  const next = { ...d, [kind]: rebuilt } as Dataset
  if (kind !== 'subjects') return next
  // subject codes are referenced by class_subjects and can_teach — carry them over
  return {
    ...next,
    class_subjects: Object.fromEntries(
      Object.entries(next.class_subjects).map(([c, list]) => [
        c,
        list.map((s) => (s === from ? to : s)),
      ]),
    ),
    teachers: Object.fromEntries(
      Object.entries(next.teachers).map(([t, info]) => [
        t,
        { ...info, can_teach: info.can_teach.map((s) => (s === from ? to : s)) },
      ]),
    ),
  }
}

const toggle = (list: string[], value: string) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

export function reducer(d: Dataset, action: Action): Dataset {
  switch (action.type) {
    case 'replace':
      return action.data

    case 'setDims': {
      const days = Math.max(1, Math.min(action.days ?? d.days, 7))
      const periods = Math.max(1, Math.min(action.periods ?? d.periods_per_day, 12))
      // every teacher grid is reshaped together, so days/periods can never
      // desync from availability — the same rule data_loader.py enforces
      return {
        ...d,
        days,
        periods_per_day: periods,
        teachers: Object.fromEntries(
          Object.entries(d.teachers).map(([t, info]) => [
            t,
            { ...info, availability: reshape(info.availability, days, periods) },
          ]),
        ),
        early_periods: d.early_periods.filter((p) => p < periods),
        late_periods: d.late_periods.filter((p) => p < periods),
        institution: {
          ...d.institution,
          breaks: d.institution.breaks.filter((b) => b.period < periods && b.day < days),
        },
      }
    }

    case 'setInstitution':
      return { ...d, institution: { ...d.institution, ...action.patch } }

    case 'setWeight':
      return { ...d, weights: { ...d.weights, [action.key]: action.value } }

    case 'setMaxConsecutive':
      return { ...d, max_consecutive_periods: action.value }

    case 'setPeriodList':
      return { ...d, [action.key]: [...action.value].sort((a, b) => a - b) }

    case 'setSolverConfig':
      return { ...d, solver_config: { ...d.solver_config, ...action.patch } }

    case 'setCount': {
      const ids = idsOf(d, action.kind)
      const n = Math.max(0, Math.min(action.n, 200))
      if (n === ids.length) return d
      if (n < ids.length)
        return ids.slice(n).reduce((acc, id) => withoutEntity(acc, action.kind, id), d)
      const taken = new Set(ids)
      let next = d
      for (let i = ids.length; i < n; i++) {
        const id = nextId(taken, action.kind)
        taken.add(id)
        next = withEntity(next, action.kind, id)
      }
      return next
    }

    case 'add':
      return withEntity(d, action.kind, action.id ?? nextId(new Set(idsOf(d, action.kind)), action.kind))

    case 'remove':
      return withoutEntity(d, action.kind, action.id)

    case 'rename':
      return renamed(d, action.kind, action.id, action.to)

    case 'patch':
      if (!(action.id in d[action.kind])) return d
      return {
        ...d,
        [action.kind]: {
          ...d[action.kind],
          [action.id]: { ...d[action.kind][action.id], ...action.patch },
        },
      }

    case 'toggleClassSubject':
      return {
        ...d,
        class_subjects: {
          ...d.class_subjects,
          [action.cls]: toggle(d.class_subjects[action.cls] ?? [], action.subject),
        },
      }

    case 'setClassSubjects':
      return { ...d, class_subjects: { ...d.class_subjects, [action.cls]: action.subjects } }

    case 'toggleCanTeach': {
      const t = d.teachers[action.teacher]
      if (!t) return d
      return {
        ...d,
        teachers: {
          ...d.teachers,
          [action.teacher]: { ...t, can_teach: toggle(t.can_teach, action.subject) },
        },
      }
    }

    case 'setAvailability': {
      const t = d.teachers[action.teacher]
      if (!t) return d
      return {
        ...d,
        teachers: { ...d.teachers, [action.teacher]: { ...t, availability: action.availability } },
      }
    }

    case 'copyAvailability': {
      const src = d.teachers[action.from]
      const dst = d.teachers[action.to]
      if (!src || !dst) return d
      return {
        ...d,
        teachers: {
          ...d.teachers,
          [action.to]: { ...dst, availability: src.availability.map((r) => [...r]) },
        },
      }
    }

    case 'addBreak':
      return {
        ...d,
        institution: {
          ...d.institution,
          breaks: [
            ...d.institution.breaks,
            { day: -1, period: Math.floor(d.periods_per_day / 2), duration: 1, name: 'Lunch' },
          ],
        },
      }

    case 'patchBreak':
      return {
        ...d,
        institution: {
          ...d.institution,
          breaks: d.institution.breaks.map((b, i) =>
            i === action.index ? { ...b, ...action.patch } : b,
          ),
        },
      }

    case 'removeBreak':
      return {
        ...d,
        institution: {
          ...d.institution,
          breaks: d.institution.breaks.filter((_, i) => i !== action.index),
        },
      }
  }
}
