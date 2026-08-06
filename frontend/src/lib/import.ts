/** Turning a spreadsheet into dataset entities. Pure functions — the server
 *  only hands back rows, every decision about what they mean happens here. */
import type { ParsedSheet } from './api'
import type { Dataset, Room, Subject, Teacher } from './types'
import { DAY_NAMES, grid } from './types'

export type Target = 'skip' | 'classes' | 'subjects' | 'teachers' | 'rooms'

export interface Field {
  key: string
  label: string
  required?: boolean
  hint?: string
}

export const FIELDS: Record<Exclude<Target, 'skip'>, Field[]> = {
  classes: [
    { key: 'id', label: 'Class name', required: true },
    { key: 'subjects', label: 'Subjects taken', hint: 'separated by ; or ,' },
  ],
  subjects: [
    { key: 'id', label: 'Subject code', required: true },
    { key: 'name', label: 'Full name' },
    { key: 'hours_per_week', label: 'Hours per week', required: true },
    { key: 'room_type', label: 'Room type' },
    { key: 'block_size', label: 'Block size', hint: 'consecutive periods per session' },
    { key: 'is_heavy', label: 'Is heavy', hint: 'yes / no' },
  ],
  teachers: [
    { key: 'id', label: 'Teacher ID', required: true },
    { key: 'name', label: 'Full name' },
    { key: 'department', label: 'Department' },
    { key: 'can_teach', label: 'Can teach', hint: 'subject codes, separated by ; or ,' },
    { key: 'unavailable', label: 'Unavailable slots', hint: 'e.g. Mon P1; Fri P6' },
  ],
  rooms: [
    { key: 'id', label: 'Room ID', required: true },
    { key: 'type', label: 'Room type', required: true },
    { key: 'capacity', label: 'Capacity' },
  ],
}

export interface SheetMapping {
  target: Target
  /** field key -> column index, -1 for "not mapped" */
  fields: Record<string, number>
}

type Cell = string | number | null

const text = (c: Cell) => (c === null || c === undefined ? '' : String(c).trim())
const num = (c: Cell) => {
  const n = Number(String(c ?? '').replace(/[^0-9.-]/g, ''))
  return Number.isFinite(n) ? n : 0
}
const bool = (c: Cell) => /^(y|yes|true|1|x)$/i.test(text(c))
export const splitList = (c: Cell) =>
  text(c)
    .split(/[;,/|]+/)
    .map((s) => s.trim())
    .filter(Boolean)

/** "Mon P1; Fri P6" -> [[0,0],[4,5]] (0-based day, 0-based period). */
export function parseUnavailable(c: Cell): [number, number][] {
  const out: [number, number][] = []
  for (const token of splitList(c)) {
    const day = DAY_NAMES.findIndex((d) => token.toLowerCase().startsWith(d.toLowerCase()))
    const period = token.match(/p?\s*(\d+)\s*$/i)
    if (day >= 0 && period) out.push([day, Number(period[1]) - 1])
  }
  return out
}

const SYNONYMS: Record<string, string[]> = {
  id: ['id', 'code', 'class', 'room', 'teacher', 'subject', 'name', 'identifier', 'staff'],
  name: ['name', 'title', 'full name', 'description'],
  hours_per_week: ['hours', 'hours per week', 'hours_per_week', 'hrs', 'weekly hours', 'periods'],
  room_type: ['room type', 'room_type', 'roomtype', 'venue', 'lab'],
  block_size: ['block', 'block size', 'block_size', 'consecutive', 'duration'],
  is_heavy: ['heavy', 'is heavy', 'is_heavy', 'difficult'],
  can_teach: ['can teach', 'can_teach', 'subjects', 'teaches', 'qualified'],
  unavailable: ['unavailable', 'not available', 'busy', 'blocked', 'off'],
  department: ['department', 'dept', 'branch'],
  type: ['type', 'room type', 'room_type', 'kind', 'category'],
  capacity: ['capacity', 'seats', 'size'],
  subjects: ['subjects', 'subject codes', 'courses', 'takes'],
}

/** Best-effort first guess. The user confirms or corrects it before merging. */
export function guessMapping(sheet: ParsedSheet): SheetMapping {
  const hay = `${sheet.name} ${sheet.headers.join(' ')}`.toLowerCase()
  const target: Target = /teacher|staff|faculty/.test(hay)
    ? 'teachers'
    : /room|venue|hall|lab/.test(hay) && !/subject|course/.test(hay)
      ? 'rooms'
      : /subject|course|paper/.test(hay)
        ? 'subjects'
        : /class|section|batch|division/.test(hay)
          ? 'classes'
          : 'skip'

  const fields: Record<string, number> = {}
  if (target !== 'skip') {
    const used = new Set<number>()
    for (const f of FIELDS[target]) {
      const options = SYNONYMS[f.key] ?? [f.key]
      const idx = sheet.headers.findIndex((h, i) => {
        if (used.has(i)) return false
        const clean = h.toLowerCase().trim()
        return options.some((o) => clean === o || clean.replace(/[_\s]+/g, ' ') === o)
      })
      fields[f.key] = idx
      if (idx >= 0) used.add(idx)
    }
    // an id column is mandatory; fall back to the first unclaimed column
    if (fields.id === undefined || fields.id < 0) {
      const first = sheet.headers.findIndex((_, i) => !used.has(i))
      fields.id = first >= 0 ? first : 0
    }
  }
  return { target, fields }
}

export interface ImportResult {
  data: Dataset
  summary: string[]
}

/**
 * Merge mapped rows into the dataset: match on the id column, update matched
 * entities in place, append unmatched ones. Nothing is ever deleted — an import
 * that misses a column should not wipe out work already done in the builder.
 */
export function applyImport(
  data: Dataset,
  sheets: ParsedSheet[],
  mapping: Record<string, SheetMapping>,
): ImportResult {
  let d: Dataset = {
    ...data,
    subjects: { ...data.subjects },
    teachers: { ...data.teachers },
    rooms: { ...data.rooms },
    classes: [...data.classes],
    class_subjects: { ...data.class_subjects },
  }
  const summary: string[] = []

  // subjects first: teachers and classes both reference subject codes
  const order: Target[] = ['subjects', 'rooms', 'classes', 'teachers']
  for (const target of order) {
    for (const sheet of sheets) {
      const map = mapping[sheet.name]
      if (!map || map.target !== target) continue
      const get = (row: Cell[], key: string): Cell => {
        const i = map.fields[key]
        return i === undefined || i < 0 ? null : (row[i] ?? null)
      }

      let added = 0
      let updated = 0
      for (const row of sheet.rows) {
        const id = text(get(row, 'id'))
        if (!id) continue

        if (target === 'subjects') {
          const existing = d.subjects[id]
          const next: Subject = {
            name: text(get(row, 'name')) || existing?.name || '',
            hours_per_week: map.fields.hours_per_week >= 0
              ? num(get(row, 'hours_per_week'))
              : (existing?.hours_per_week ?? 3),
            room_type: text(get(row, 'room_type')) || existing?.room_type || 'standard',
            block_size: map.fields.block_size >= 0
              ? Math.max(1, num(get(row, 'block_size')))
              : (existing?.block_size ?? 1),
            is_heavy: map.fields.is_heavy >= 0 ? bool(get(row, 'is_heavy')) : (existing?.is_heavy ?? false),
          }
          d.subjects[id] = next
          existing ? updated++ : added++
        } else if (target === 'rooms') {
          const existing = d.rooms[id]
          const next: Room = {
            type: text(get(row, 'type')) || existing?.type || 'standard',
            capacity: map.fields.capacity >= 0 ? num(get(row, 'capacity')) : (existing?.capacity ?? 30),
          }
          d.rooms[id] = next
          existing ? updated++ : added++
        } else if (target === 'classes') {
          const existed = d.classes.includes(id)
          if (!existed) d.classes.push(id)
          const listed = splitList(get(row, 'subjects')).filter((s) => s in d.subjects)
          if (listed.length) d.class_subjects[id] = listed
          else if (!existed) d.class_subjects[id] = []
          existed ? updated++ : added++
        } else {
          const existing = d.teachers[id]
          const listed = splitList(get(row, 'can_teach')).filter((s) => s in d.subjects)
          const availability = grid(d.days, d.periods_per_day)
          for (const [day, period] of parseUnavailable(get(row, 'unavailable')))
            if (day < d.days && period >= 0 && period < d.periods_per_day) availability[day][period] = 0
          const next: Teacher = {
            name: text(get(row, 'name')) || existing?.name || '',
            department: text(get(row, 'department')) || existing?.department || '',
            can_teach: listed.length ? listed : (existing?.can_teach ?? []),
            // only overwrite a grid the sheet actually said something about
            availability:
              map.fields.unavailable >= 0 || !existing ? availability : existing.availability,
          }
          d.teachers[id] = next
          existing ? updated++ : added++
        }
      }
      if (added || updated)
        summary.push(
          `${sheet.name} → ${target}: ${added} added, ${updated} updated`,
        )
    }
  }

  // any class the import created still needs a subject list
  for (const c of d.classes) if (!d.class_subjects[c]) d.class_subjects[c] = []

  return { data: d, summary }
}
