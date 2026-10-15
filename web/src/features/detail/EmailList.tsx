import type { EmailItem } from '@/api/types'

const shortDate = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' })

/** The emails behind an application. Snippets come from untrusted mail, so they stay plain text. */
export function EmailList({ emails }: { emails: EmailItem[] }) {
  // Manual applications, or ones matched by thread, can have none.
  if (emails.length === 0) return <p className="text-muted">No emails</p>

  return (
    <ul className="flex flex-col gap-2">
      {emails.map((email) => (
        <li key={email.id}>
          <article className="rounded-lg border bg-surface p-3">
            <div className="flex items-baseline justify-between gap-3">
              <h4 className="min-w-0 font-medium break-words">{email.subject}</h4>
              <time
                dateTime={email.received_at}
                className="shrink-0 font-mono text-label text-muted"
              >
                {shortDate.format(new Date(email.received_at))}
              </time>
            </div>
            <p
              className="mt-0.5 truncate font-mono text-label text-muted"
              title={email.from_address}
            >
              {email.from_address}
            </p>
            <p className="mt-2 break-words whitespace-pre-line">{email.snippet}</p>
          </article>
        </li>
      ))}
    </ul>
  )
}
