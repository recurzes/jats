import type { ApplicationSummary, Status } from '@/api/types'
import { STATUS_ORDER } from '@/shared/lib/statuses'

export type Columns = Record<Status, ApplicationSummary[]>

// Newest first. Ties fall back to id, so cards keep their place between polls.
function newestFirst(a: ApplicationSummary, b: ApplicationSummary) {
  const byTime = Date.parse(b.last_event_at) - Date.parse(a.last_event_at)
  if (byTime !== 0) return byTime
  return a.id < b.id ? -1 : a.id > b.id ? 1 : 0
}

/** One list per status, each sorted newest first. Every status has a key, even when empty. */
export function groupByStatus(list: readonly ApplicationSummary[]): Columns {
  const columns = Object.fromEntries(
    STATUS_ORDER.map((status) => [status, []]),
  ) as unknown as Columns
  for (const application of list) columns[application.status].push(application)
  for (const status of STATUS_ORDER) columns[status].sort(newestFirst)
  return columns
}
