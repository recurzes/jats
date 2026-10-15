import type { Status } from '@/api/types'
import { STATUSES } from '@/shared/lib/statuses'
import { cn } from '@/shared/lib/utils'

/** The status colour as a dot. Decorative: always show the status label next to it. */
export function StatusDot({ status, className }: { status: Status; className?: string }) {
  return (
    <span
      aria-hidden
      data-status={status}
      className={cn(
        'inline-block size-2.5 shrink-0 rounded-full',
        STATUSES[status].dotClass,
        className,
      )}
    />
  )
}
