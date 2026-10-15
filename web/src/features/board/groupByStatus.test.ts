import type { ApplicationSummary } from '@/api/types'
import { groupByStatus } from '@/features/board/groupByStatus'
import { applications } from '@/mocks/fixtures'

const ids = (list: ApplicationSummary[]) => list.map((application) => application.id)

function application(changes: Partial<ApplicationSummary>): ApplicationSummary {
  return { ...applications[0], ...changes }
}

test('an empty list gives four empty columns', () => {
  expect(groupByStatus([])).toEqual({ acknowledged: [], replied: [], update: [], rejected: [] })
})

test('one status only still returns every key', () => {
  const list = [application({ id: 'a', status: 'rejected' })]

  const columns = groupByStatus(list)

  expect(Object.keys(columns)).toEqual(['acknowledged', 'replied', 'update', 'rejected'])
  expect(ids(columns.rejected)).toEqual(['a'])
  expect(columns.acknowledged).toEqual([])
})

test('sorts each column newest first', () => {
  const list = [
    application({ id: 'old', status: 'replied', last_event_at: '2026-10-01T00:00:00Z' }),
    application({ id: 'new', status: 'replied', last_event_at: '2026-10-03T00:00:00Z' }),
    application({ id: 'mid', status: 'replied', last_event_at: '2026-10-02T00:00:00Z' }),
  ]

  expect(ids(groupByStatus(list).replied)).toEqual(['new', 'mid', 'old'])
})

test('ties sort by id, whatever the input order', () => {
  const at = '2026-10-01T00:00:00Z'
  const list = [
    application({ id: 'c', status: 'update', last_event_at: at }),
    application({ id: 'a', status: 'update', last_event_at: at }),
    application({ id: 'b', status: 'update', last_event_at: at }),
  ]

  expect(ids(groupByStatus(list).update)).toEqual(['a', 'b', 'c'])
  expect(ids(groupByStatus([...list].reverse()).update)).toEqual(['a', 'b', 'c'])
})

test('compares times, not strings', () => {
  const list = [
    application({ id: 'earlier', status: 'replied', last_event_at: '2026-10-01T10:00:00Z' }),
    // The same day, later, written with an offset and microseconds.
    application({
      id: 'later',
      status: 'replied',
      last_event_at: '2026-10-01T09:00:00.123456-03:00',
    }),
  ]

  expect(ids(groupByStatus(list).replied)).toEqual(['later', 'earlier'])
})

test('groups the fixtures', () => {
  const columns = groupByStatus(applications)

  expect(columns.acknowledged).toHaveLength(3)
  expect(columns.replied).toHaveLength(2)
  expect(columns.update).toHaveLength(2)
  expect(columns.rejected).toHaveLength(2)
})
