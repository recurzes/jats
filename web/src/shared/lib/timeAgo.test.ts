import { timeAgo } from '@/shared/lib/timeAgo'

const now = new Date('2026-10-14T12:00:00Z')
const before = (seconds: number) => new Date(now.getTime() - seconds * 1000)

test('seconds', () => {
  expect(timeAgo(now, now)).toBe('now')
  expect(timeAgo(before(30), now)).toBe('30 seconds ago')
})

test('minutes, rounded down', () => {
  expect(timeAgo(before(60), now)).toBe('1 minute ago')
  expect(timeAgo(before(2 * 60 + 59), now)).toBe('2 minutes ago')
})

test('hours', () => {
  expect(timeAgo(before(3 * 60 * 60), now)).toBe('3 hours ago')
})

test('days, with "yesterday" for one', () => {
  expect(timeAgo(before(24 * 60 * 60), now)).toBe('yesterday')
  expect(timeAgo(before(4 * 24 * 60 * 60), now)).toBe('4 days ago')
})

test('months and years', () => {
  expect(timeAgo(before(45 * 24 * 60 * 60), now)).toBe('last month')
  expect(timeAgo(before(800 * 24 * 60 * 60), now)).toBe('2 years ago')
})

test('future dates', () => {
  expect(timeAgo(new Date(now.getTime() + 5 * 60 * 1000), now)).toBe('in 5 minutes')
  expect(timeAgo(new Date(now.getTime() + 24 * 60 * 60 * 1000), now)).toBe('tomorrow')
})

test('accepts the ISO string the API sends', () => {
  expect(timeAgo('2026-10-14T11:58:00Z', now)).toBe('2 minutes ago')
})
