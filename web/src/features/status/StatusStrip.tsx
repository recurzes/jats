import type { DeviceStatus, LastSync, QueueStatus } from '@/api/types'
import { StatusPill, type StatusTone } from '@/features/status/StatusPill'
import { useStatus } from '@/features/status/useStatus'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/shared/components/ui/tooltip'
import { timeAgo } from '@/shared/lib/timeAgo'

interface Pill {
  tone: StatusTone
  text: string
}

// Not connected and needs reauth arrive in branches 69 and 72.
function gmailPill(lastSync: LastSync | null, now: Date): Pill {
  if (!lastSync) return { tone: 'warning', text: 'Gmail not synced yet' }
  // finished_at is null while a sync is still running.
  if (!lastSync.finished_at) {
    return { tone: 'good', text: `Gmail sync started ${timeAgo(lastSync.started_at, now)}` }
  }
  const when = timeAgo(lastSync.finished_at, now)
  // fallback_full and skipped_locked are fine: the sync caught up, or another one was running.
  return lastSync.result === 'error'
    ? { tone: 'error', text: `Gmail sync failed ${when}` }
    : { tone: 'good', text: `Gmail synced ${when}` }
}

// `device` is never null: a missing device looks like one that never polled.
function printerPill({ last_seen_at, online }: DeviceStatus, now: Date): Pill & { detail: string } {
  if (!last_seen_at) {
    return { tone: 'warning', text: 'Printer: never seen', detail: 'No printer has polled yet' }
  }
  const detail = `Last seen ${timeAgo(last_seen_at, now)}`
  // The backend counts a printer as online when it polled in the last 2 minutes.
  return online
    ? { tone: 'good', text: 'Printer online', detail }
    : { tone: 'error', text: 'Printer offline', detail }
}

function queuePill({ pending, failed }: QueueStatus): Pill {
  return failed > 0
    ? { tone: 'warning', text: `Print queue: ${pending}, ${failed} failed` }
    : { tone: 'good', text: `Print queue: ${pending}` }
}

/** Gmail sync, printer and print queue at a glance. Lives in the header. */
export function StatusStrip() {
  const { data, isError, dataUpdatedAt } = useStatus()

  if (!data) {
    // Hidden while loading, so the header does not flash a placeholder.
    return isError ? (
      <StatusPill tone="error" className="self-center">
        Status unavailable
      </StatusPill>
    ) : null
  }

  // Times are "as of the last poll". Reading dataUpdatedAt also re-renders on every poll, even
  // when the data is unchanged, so "2 minutes ago" keeps moving.
  const now = new Date(dataUpdatedAt)
  const gmail = gmailPill(data.last_sync, now)
  const printer = printerPill(data.device, now)
  const queue = queuePill(data.queue)

  return (
    <ul aria-label="System status" className="flex flex-wrap items-center gap-2">
      <li>
        <StatusPill tone={gmail.tone}>{gmail.text}</StatusPill>
      </li>
      <li>
        <Tooltip>
          <TooltipTrigger asChild>
            {/* Focusable, so the tooltip opens from the keyboard too. */}
            <StatusPill
              tone={printer.tone}
              tabIndex={0}
              className="cursor-default outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              {printer.text}
            </StatusPill>
          </TooltipTrigger>
          <TooltipContent>{printer.detail}</TooltipContent>
        </Tooltip>
      </li>
      <li>
        <StatusPill tone={queue.tone}>{queue.text}</StatusPill>
      </li>
    </ul>
  )
}
