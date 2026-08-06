/** Instant feedback mirroring pre_validate_input in timetable_solver/validator.py.
 *
 *  Deliberate duplication: the server stays authoritative and its INVALID errors
 *  are shown verbatim. This copy exists so that typing `hours = 5` on a 3-period
 *  lab turns red now, instead of after a 60-second solve that ends in INFEASIBLE.
 */
import type { Dataset } from './types'

export interface Issue {
  level: 'error' | 'warn'
  message: string
  tab: string
  id?: string
}

/** Slots a break removes from every class's week. day: -1 means all days. */
export function blockedSlots(d: Dataset): number {
  return d.institution.breaks.reduce(
    (n, b) => n + (b.duration || 1) * (b.day === -1 ? d.days : 1),
    0,
  )
}

export function validate(d: Dataset): Issue[] {
  const issues: Issue[] = []
  const subjectIds = Object.keys(d.subjects)
  const teacherIds = Object.keys(d.teachers)
  const roomTypes = new Set(Object.values(d.rooms).map((r) => r.type))
  const slotsPerClass = d.days * d.periods_per_day - blockedSlots(d)

  if (d.classes.length === 0) issues.push({ level: 'error', message: 'No classes defined.', tab: 'classes' })
  if (subjectIds.length === 0) issues.push({ level: 'error', message: 'No subjects defined.', tab: 'subjects' })
  if (teacherIds.length === 0) issues.push({ level: 'error', message: 'No teachers defined.', tab: 'teachers' })
  if (Object.keys(d.rooms).length === 0)
    issues.push({ level: 'error', message: 'No rooms defined.', tab: 'rooms' })

  for (const [code, s] of Object.entries(d.subjects)) {
    if (!teacherIds.some((t) => d.teachers[t].can_teach.includes(code)))
      issues.push({
        level: 'error',
        message: `Subject "${code}" has no qualified teacher — nobody can teach it.`,
        tab: 'teachers',
        id: code,
      })
    if (s.block_size > 1 && s.hours_per_week % s.block_size !== 0)
      issues.push({
        level: 'error',
        message: `Subject "${code}": ${s.hours_per_week} hours/week cannot be split into blocks of ${s.block_size}.`,
        tab: 'subjects',
        id: code,
      })
    if (s.hours_per_week <= 0)
      issues.push({
        level: 'error',
        message: `Subject "${code}" has no weekly hours.`,
        tab: 'subjects',
        id: code,
      })
    if (roomTypes.size > 0 && !roomTypes.has(s.room_type))
      issues.push({
        level: 'error',
        message: `Subject "${code}" needs a "${s.room_type}" room, but no room has that type.`,
        tab: 'rooms',
        id: code,
      })
    if (s.block_size > d.periods_per_day)
      issues.push({
        level: 'error',
        message: `Subject "${code}" needs ${s.block_size} consecutive periods but the day is only ${d.periods_per_day} long.`,
        tab: 'subjects',
        id: code,
      })
  }

  if (d.classes.length > Object.keys(d.rooms).length)
    issues.push({
      level: 'error',
      message: `${d.classes.length} classes but only ${Object.keys(d.rooms).length} rooms — they cannot all be taught at once.`,
      tab: 'rooms',
    })

  let demand = 0
  for (const c of d.classes) {
    const list = d.class_subjects[c] ?? []
    if (list.length === 0) {
      issues.push({ level: 'error', message: `Class "${c}" has no subjects assigned.`, tab: 'classes', id: c })
      continue
    }
    const hours = list.reduce((n, s) => n + (d.subjects[s]?.hours_per_week ?? 0), 0)
    demand += hours
    if (hours > slotsPerClass)
      issues.push({
        level: 'error',
        message: `Class "${c}" needs ${hours} hours but the week only has ${slotsPerClass} teachable slots.`,
        tab: 'classes',
        id: c,
      })
    else if (hours > slotsPerClass * 0.95)
      issues.push({
        level: 'warn',
        message: `Class "${c}" fills ${hours} of ${slotsPerClass} slots — very tight, the solver may need longer.`,
        tab: 'classes',
        id: c,
      })
  }

  let capacity = 0
  for (const t of teacherIds) {
    const info = d.teachers[t]
    const free = info.availability.flat().reduce((a: number, b: number) => a + b, 0)
    capacity += free
    if (free === 0)
      issues.push({
        level: 'error',
        message: `Teacher "${t}" is unavailable every period.`,
        tab: 'teachers',
        id: t,
      })
    if (info.can_teach.length === 0)
      issues.push({
        level: 'warn',
        message: `Teacher "${t}" is not assigned to any subject.`,
        tab: 'teachers',
        id: t,
      })
    if (info.availability.length !== d.days || info.availability.some((r) => r.length !== d.periods_per_day))
      issues.push({
        level: 'warn',
        message: `Teacher "${t}" has an availability grid that does not match ${d.days}×${d.periods_per_day} — it will be reshaped on save.`,
        tab: 'teachers',
        id: t,
      })
  }

  if (teacherIds.length && demand > capacity)
    issues.push({
      level: 'error',
      message: `Teachers can cover ${capacity} slots but ${demand} hours of teaching are required (short by ${demand - capacity}).`,
      tab: 'teachers',
    })
  else if (teacherIds.length && demand > capacity * 0.9)
    issues.push({
      level: 'warn',
      message: `Teacher capacity is tight: ${demand} hours needed against ${capacity} available slots.`,
      tab: 'teachers',
    })

  return issues
}
