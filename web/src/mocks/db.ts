import type { ApplicationDetail, StatusResponse } from '@/api/types'
import { applicationDetail, applications, status } from '@/mocks/fixtures'

interface MockDb {
  applications: ApplicationDetail[]
  // Applications with a reprint waiting to print, so a second one answers 409.
  pendingReprints: Set<string>
  status: StatusResponse
}

// A detail for each fixture that has none: one email (if it has one) and the event that made it.
function toDetail(summary: (typeof applications)[number]): ApplicationDetail {
  if (summary.id === applicationDetail.id) return structuredClone(applicationDetail)

  const emailId = `${summary.id}-email`
  return {
    ...summary,
    first_seen_at: summary.last_event_at,
    emails:
      summary.last_email_subject && summary.last_email_at
        ? [
            {
              id: emailId,
              subject: summary.last_email_subject,
              from_address: `jobs@${summary.company.toLowerCase().replace(/[^a-z]/g, '')}.example`,
              snippet: `Hello, this is about your application to ${summary.company}.`,
              received_at: summary.last_email_at,
            },
          ]
        : [],
    status_events: [
      {
        id: `${summary.id}-event`,
        from_status: null,
        to_status: summary.status,
        source: summary.last_email_at ? 'ai' : 'manual',
        email_id: summary.last_email_at ? emailId : null,
        created_at: summary.last_event_at,
      },
    ],
  }
}

function seed(): MockDb {
  return {
    applications: applications.map(toDetail),
    pendingReprints: new Set(),
    status: structuredClone(status),
  }
}

/** Mutated by the handlers. Changes last until the page reloads, or `resetDb()` in tests. */
export const db: MockDb = seed()

export function resetDb() {
  Object.assign(db, seed())
}
