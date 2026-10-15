import type { ApplicationSummary } from '@/api/types'
import { Badge } from '@/shared/components/ui/badge'
import { Skeleton } from '@/shared/components/ui/skeleton'

const shortDate = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' })

/** Who, what role, and the latest email. The mockup's Printed badge is left out of V1. */
export function ApplicationCard({ application }: { application: ApplicationSummary }) {
  const { company, role, needs_review, last_email_subject, last_email_at } = application
  // Both are null when no email has arrived yet.
  const hasEmail = last_email_subject !== null || last_email_at !== null

  return (
    <article className="rounded-lg border bg-surface p-3 shadow-xs">
      <div className="flex items-start justify-between gap-2">
        <h3 className="min-w-0 text-card-title leading-snug font-semibold break-words">
          {company}
        </h3>
        {needs_review && <Badge variant="review">Needs review</Badge>}
      </div>
      {role && <p className="mt-0.5 break-words text-muted">{role}</p>}
      {hasEmail && (
        <div className="mt-3 border-t pt-2.5">
          {last_email_subject && (
            <p className="truncate" title={last_email_subject}>
              {last_email_subject}
            </p>
          )}
          {last_email_at && (
            <time dateTime={last_email_at} className="font-mono text-label text-muted">
              {shortDate.format(new Date(last_email_at))}
            </time>
          )}
        </div>
      )}
    </article>
  )
}

/** Holds a card's place during the first load. */
export function ApplicationCardSkeleton() {
  return (
    <div className="rounded-lg border bg-surface p-3">
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="mt-2 h-3.5 w-1/2" />
      <div className="mt-3 border-t pt-2.5">
        <Skeleton className="h-3.5 w-5/6" />
        <Skeleton className="mt-2 h-3 w-12" />
      </div>
    </div>
  )
}
