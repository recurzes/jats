import type { StatusEvent } from '@/api/types'
import { StatusDot } from '@/shared/components/StatusDot'
import { STATUSES } from '@/shared/lib/statuses'

const dateTime = new Intl.DateTimeFormat('en', {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function describe({ from_status, to_status }: StatusEvent) {
  const to = STATUSES[to_status].label
  // from_status is null on the event that created the application.
  return from_status === null ? `Started as ${to}` : `${STATUSES[from_status].label} to ${to}`
}

/** How the application got to its status. `events` arrive newest first, as the API sends them. */
export function StatusHistory({ events }: { events: StatusEvent[] }) {
  return (
    <ol className="flex flex-col">
      {events.map((event, index) => (
        <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
          {/* The line joins this dot to the next, older event. */}
          {index < events.length - 1 && (
            <span aria-hidden className="absolute top-4 bottom-0 left-[4.5px] w-px bg-border" />
          )}
          <StatusDot status={event.to_status} className="mt-1" />
          <div className="min-w-0">
            <p className="font-medium">{describe(event)}</p>
            <p className="text-label text-muted">
              <time dateTime={event.created_at} className="font-mono">
                {dateTime.format(new Date(event.created_at))}
              </time>
              {' · '}
              {event.source === 'ai' ? 'from email' : 'manual'}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}
