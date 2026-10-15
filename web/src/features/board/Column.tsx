import { useId } from 'react'
import type { ApplicationSummary, Status } from '@/api/types'
import { ApplicationCard, ApplicationCardSkeleton } from '@/features/board/ApplicationCard'
import { StatusDot } from '@/shared/components/StatusDot'
import { STATUSES } from '@/shared/lib/statuses'

/** One status. Leave out `applications` while the first load runs to show skeleton cards. */
export function Column({
  status,
  applications,
}: {
  status: Status
  applications?: ApplicationSummary[]
}) {
  const headingId = useId()

  return (
    // min-w-0 lets long names and subjects wrap or truncate instead of widening the column.
    <section aria-labelledby={headingId} className="min-w-0 rounded-xl bg-column p-3">
      <h2 id={headingId} className="flex items-center gap-2 px-1 pb-3 font-semibold">
        <StatusDot status={status} />
        {STATUSES[status].label}
        {applications && (
          <span className="ml-auto font-mono text-label font-normal text-muted">
            {applications.length}
          </span>
        )}
      </h2>
      {!applications ? (
        <div className="flex flex-col gap-2">
          <ApplicationCardSkeleton />
          <ApplicationCardSkeleton />
        </div>
      ) : applications.length === 0 ? (
        <p className="px-1 pb-1 text-muted">Nothing here yet</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {applications.map((application) => (
            <li key={application.id}>
              <ApplicationCard application={application} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
