import { STATUS_ORDER, STATUSES } from '@/shared/lib/statuses'

test('every status has an entry, and the order lists each one once', () => {
  expect(STATUS_ORDER).toEqual(['acknowledged', 'replied', 'update', 'rejected'])
  expect(Object.keys(STATUSES).sort()).toEqual([...STATUS_ORDER].sort())

  for (const status of STATUS_ORDER) {
    expect(STATUSES[status].label).toBeTruthy()
    expect(STATUSES[status].dotClass).toBe(`bg-status-${status}`)
  }
})
