/** Self-checks for the pure logic. No test framework: `npm run check` bundles
 *  this with the esbuild that already ships inside Vite, then runs it. */
import assert from 'node:assert/strict'
import { reducer } from './builderReducer'
import { applyImport, guessMapping, parseUnavailable } from './import'
import { normalize, reshape } from './types'
import { validate } from './validate'

const base = normalize({
  days: 2,
  periods_per_day: 3,
  classes: ['C1'],
  class_subjects: { C1: ['MATH'] },
  subjects: { MATH: { hours_per_week: 2, room_type: 'standard' } },
  teachers: { T1: { can_teach: ['MATH'], availability: [[1, 1, 1], [1, 1, 1]] } },
  rooms: { R1: { type: 'standard' } },
})

// ---------------------------------------------------------------- normalize
assert.equal(base.subjects.MATH.block_size, 1, 'block_size defaults to 1')
assert.deepEqual(reshape([[1, 1, 1, 1]], 2, 3), [[1, 1, 1], [1, 1, 1]], 'reshape pads and truncates')
assert.equal(
  normalize({ classes: [], subjects: { L: { hours_per_week: 3, is_double_period: true } }, teachers: {} })
    .subjects.L.block_size,
  2,
  'legacy is_double_period becomes block_size 2',
)

// ------------------------------------------------------------------ reducer
{
  const d = reducer(base, { type: 'setCount', kind: 'teachers', n: 3 })
  assert.equal(Object.keys(d.teachers).length, 3, 'setCount grows')
  assert.ok(!('T1' in reducer(d, { type: 'setCount', kind: 'teachers', n: 0 }).teachers), 'setCount shrinks')
  assert.deepEqual(d.teachers.T02.availability, [[1, 1, 1], [1, 1, 1]], 'new teachers get a correct grid')
}
{
  // renaming a subject must follow through everywhere it is referenced
  const d = reducer(base, { type: 'rename', kind: 'subjects', id: 'MATH', to: 'M101' })
  assert.deepEqual(d.class_subjects.C1, ['M101'], 'rename updates class_subjects')
  assert.deepEqual(d.teachers.T1.can_teach, ['M101'], 'rename updates can_teach')
  assert.ok(!('MATH' in d.subjects))
}
{
  const d = reducer(base, { type: 'remove', kind: 'subjects', id: 'MATH' })
  assert.deepEqual(d.class_subjects.C1, [], 'deleting a subject unlinks it from classes')
  assert.deepEqual(d.teachers.T1.can_teach, [], 'deleting a subject unlinks it from teachers')
}
{
  const d = reducer(base, { type: 'rename', kind: 'classes', id: 'C1', to: 'S3-A' })
  assert.deepEqual(d.classes, ['S3-A'])
  assert.deepEqual(d.class_subjects['S3-A'], ['MATH'], 'class rename carries its subject list')
}
{
  // dims and availability must never be able to disagree
  const d = reducer(base, { type: 'setDims', days: 4, periods: 5 })
  assert.equal(d.teachers.T1.availability.length, 4)
  assert.equal(d.teachers.T1.availability[0].length, 5)
}
assert.equal(
  reducer(base, { type: 'rename', kind: 'subjects', id: 'MATH', to: '' }).subjects.MATH.hours_per_week,
  2,
  'an empty rename is ignored',
)

// ----------------------------------------------------------------- validate
assert.deepEqual(validate(base), [], 'the base dataset is clean')
{
  const bad = reducer(base, { type: 'patch', kind: 'subjects', id: 'MATH', patch: { block_size: 3, hours_per_week: 4 } })
  assert.ok(
    validate(bad).some((i) => i.level === 'error' && i.message.includes('blocks of 3')),
    'hours must divide by block size',
  )
}
{
  const bad = reducer(base, { type: 'patch', kind: 'subjects', id: 'MATH', patch: { room_type: 'lab' } })
  assert.ok(validate(bad).some((i) => i.message.includes('"lab" room')), 'room type must exist')
}
{
  const bad = reducer(base, { type: 'toggleCanTeach', teacher: 'T1', subject: 'MATH' })
  assert.ok(validate(bad).some((i) => i.message.includes('no qualified teacher')))
}
{
  // 1 hour x 1 class needs 1 slot; a 1x1 week with a full-day break leaves none
  const tight = reducer(base, { type: 'setDims', days: 1, periods: 1 })
  assert.ok(validate(tight).some((i) => i.level === 'error' && i.message.includes('teachable slots')))
}

// ------------------------------------------------------------------- import
assert.deepEqual(parseUnavailable('Mon P1; Fri P6'), [[0, 0], [4, 5]])
assert.deepEqual(parseUnavailable(''), [])
assert.deepEqual(parseUnavailable('nonsense'), [], 'unparseable tokens are dropped, not guessed')
{
  const sheet = {
    name: 'Teachers',
    headers: ['id', 'name', 'can teach', 'unavailable'],
    rows: [
      ['T1', 'Renamed Person', 'MATH', 'Mon P2'],
      ['T9', 'New Person', 'MATH', ''],
    ] as (string | number | null)[][],
  }
  const map = guessMapping(sheet)
  assert.equal(map.target, 'teachers', 'sheet name picks the entity')
  assert.equal(map.fields.can_teach, 2, 'header synonyms map columns')

  const { data, summary } = applyImport(base, [sheet], { Teachers: map })
  assert.equal(Object.keys(data.teachers).length, 2, 'unmatched rows are appended')
  assert.equal(data.teachers.T1.name, 'Renamed Person', 'matched rows are updated in place')
  assert.equal(data.teachers.T1.availability[0][1], 0, 'unavailable slots are punched out')
  assert.equal(data.teachers.T9.availability[0][1], 1, 'a blank unavailable column means free')
  assert.ok(summary[0].includes('1 added, 1 updated'))
  assert.equal(base.teachers.T1.name, '', 'the input dataset is not mutated')
}
{
  // a subject the sheet references but the dataset does not have is dropped,
  // rather than silently creating a phantom the solver cannot schedule
  const sheet = {
    name: 'Staff',
    headers: ['id', 'subjects'],
    rows: [['T5', 'MATH; GHOST']] as (string | number | null)[][],
  }
  const { data } = applyImport(base, [sheet], {
    Staff: { target: 'teachers', fields: { id: 0, can_teach: 1, name: -1, department: -1, unavailable: -1 } },
  })
  assert.deepEqual(data.teachers.T5.can_teach, ['MATH'])
}

console.log('ok — all checks passed')
