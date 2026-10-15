import { http, HttpResponse } from 'msw'
import type {
  ApiErrorBody,
  ApplicationDetail,
  ApplicationPatch,
  ApplicationSummary,
  ConnectUrl,
  DeviceCreated,
  ReprintQueued,
  StatusResponse,
  SyncStarted,
} from '@/api/types'
import { config } from '@/config'
import { db } from '@/mocks/db'

const api = (path: string) => `${config.apiUrl}${path}`

// A plain Response, so a handler can return it next to its typed success response.
function apiError(status: number, code: string, message: string): Response {
  return HttpResponse.json<ApiErrorBody>({ error: { code, message } }, { status })
}

const notFound = () => apiError(404, 'NOT_FOUND', 'Application not found')

function toSummary({
  first_seen_at: _firstSeen,
  emails: _emails,
  status_events: _events,
  ...summary
}: ApplicationDetail): ApplicationSummary {
  return summary
}

function find(id: unknown) {
  return db.applications.find((application) => application.id === id)
}

function byLastEventDesc(a: ApplicationDetail, b: ApplicationDetail) {
  return b.last_event_at.localeCompare(a.last_event_at)
}

export const applicationHandlers = [
  http.get(api('/applications'), ({ request }) => {
    const params = new URL(request.url).searchParams
    const status = params.get('status')
    const needsReview = params.get('needs_review')

    const list = db.applications
      .filter((application) => !status || application.status === status)
      .filter((application) => !needsReview || String(application.needs_review) === needsReview)
      .sort(byLastEventDesc)
      .map(toSummary)
    return HttpResponse.json<ApplicationSummary[]>(list)
  }),

  http.get(api('/applications/:id'), ({ params }) => {
    const application = find(params.id)
    return application ? HttpResponse.json<ApplicationDetail>(application) : notFound()
  }),

  http.patch(api('/applications/:id'), async ({ params, request }) => {
    const application = find(params.id)
    if (!application) return notFound()

    const changes = (await request.json()) as ApplicationPatch
    const now = new Date().toISOString()

    if (changes.company !== undefined) application.company = changes.company
    if (changes.role !== undefined) application.role = changes.role || null
    if (changes.status !== undefined) {
      if (changes.status !== application.status) {
        application.status_events.unshift({
          id: crypto.randomUUID(),
          from_status: application.status,
          to_status: changes.status,
          source: 'manual',
          email_id: null,
          created_at: now,
        })
        application.status = changes.status
        application.last_event_at = now
      }
      // Like the real API: sending a status confirms it, even when it is unchanged.
      application.needs_review = false
    }
    if (changes.needs_review !== undefined) application.needs_review = changes.needs_review

    return HttpResponse.json<ApplicationDetail>(application)
  }),

  http.post(api('/applications/:id/reprint'), ({ params }) => {
    const application = find(params.id)
    if (!application) return notFound()

    // Nothing prints in mock mode, so every reprint after the first stays pending.
    if (db.pendingReprints.has(application.id)) {
      return apiError(409, 'REPRINT_PENDING', 'A reprint for this application is already queued')
    }
    db.pendingReprints.add(application.id)
    return HttpResponse.json<ReprintQueued>({ job_id: crypto.randomUUID() }, { status: 201 })
  }),
]

export const miscHandlers = [
  http.get(api('/status'), () => HttpResponse.json<StatusResponse>(db.status)),

  http.post(api('/sync'), () => {
    if (db.status.gmail.state === 'not_connected') {
      return apiError(409, 'GMAIL_NOT_CONNECTED', 'No Gmail account is connected')
    }
    if (db.status.gmail.state === 'needs_reauth') {
      return apiError(409, 'GMAIL_NEEDS_REAUTH', 'Gmail has to be connected again')
    }
    // Nothing runs in the background here, so record a sync that finished at once.
    const now = new Date().toISOString()
    db.status.last_sync = {
      started_at: now,
      finished_at: now,
      result: 'ok',
      trigger: 'manual',
      error: null,
    }
    return HttpResponse.json<SyncStarted>({ status: 'started' }, { status: 202 })
  }),

  http.post(api('/devices'), async ({ request }) => {
    const { name } = (await request.json()) as { name?: string }
    if (!name?.trim()) {
      return apiError(422, 'VALIDATION', 'body.name: String should have at least 1 character')
    }
    const key = `mock-${crypto.randomUUID().replaceAll('-', '')}`
    return HttpResponse.json<DeviceCreated>(
      { id: crypto.randomUUID(), name: name.trim(), key },
      { status: 201 },
    )
  }),

  // Points back into the app, so the connect flow runs without Google.
  http.get(api('/auth/google/start'), () =>
    HttpResponse.json<ConnectUrl>({ url: '/?gmail=connected' }),
  ),
]

export const handlers = [...applicationHandlers, ...miscHandlers]
