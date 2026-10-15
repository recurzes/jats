// Largest unit first. Months and years are close enough for "how long ago".
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 365 * 24 * 60 * 60],
  ['month', 30 * 24 * 60 * 60],
  ['day', 24 * 60 * 60],
  ['hour', 60 * 60],
  ['minute', 60],
  ['second', 1],
]

// numeric: "auto" says "yesterday" instead of "1 day ago".
const format = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "2 minutes ago", "yesterday", "in 3 hours". Takes a Date or the ISO string the API sends. */
export function timeAgo(date: Date | string, now: Date = new Date()) {
  const seconds = (new Date(date).getTime() - now.getTime()) / 1000
  const [unit, size] = UNITS.find(([, size]) => Math.abs(seconds) >= size) ?? UNITS.at(-1)!
  // Rounds toward zero, so 119 seconds is still "1 minute ago". `|| 0` turns -0 into 0 ("now").
  return format.format(Math.trunc(seconds / size) || 0, unit)
}
