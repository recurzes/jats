// Handwritten from api/app/**/schemas.py. Replaced by types generated from contracts/openapi.json
// in branch 87. Dates are ISO strings: parse them where they are shown, not here.

export type Status = 'acknowledged' | 'replied' | 'update' | 'rejected'

export interface ApplicationSummary {
  id: string
  company: string
  role: string | null
  status: Status
  needs_review: boolean
  last_event_at: string
  // null for an application that has no email.
  last_email_subject: string | null
  last_email_at: string | null
}

export interface EmailItem {
  id: string
  subject: string
  from_address: string
  snippet: string
  received_at: string
}

export type EventSource = 'ai' | 'manual'

export interface StatusEvent {
  id: string
  // null on the event that created the application.
  from_status: Status | null
  to_status: Status
  source: EventSource
  // null for a manual change.
  email_id: string | null
  created_at: string
}

/** Emails and status events are newest first. */
export interface ApplicationDetail extends ApplicationSummary {
  first_seen_at: string
  emails: EmailItem[]
  status_events: StatusEvent[]
}

export interface ApplicationFilters {
  status?: Status
  needs_review?: boolean
}

/** Only the fields that are sent change. `role: null` clears the role. */
export interface ApplicationPatch {
  status?: Status
  company?: string
  role?: string | null
  needs_review?: boolean
}

export interface ReprintQueued {
  job_id: string
}

export type SyncResult = 'ok' | 'error' | 'fallback_full' | 'skipped_locked'
export type SyncTrigger = 'schedule' | 'manual'

export interface LastSync {
  started_at: string
  // Both null while the sync is still running.
  finished_at: string | null
  result: SyncResult | null
  trigger: SyncTrigger
  error: string | null
}

export type GmailState = 'ok' | 'needs_reauth' | 'not_connected'

export interface GmailStatus {
  state: GmailState
  // null while no account is connected.
  address: string | null
}

export interface DeviceStatus {
  // null while no device has ever polled.
  last_seen_at: string | null
  // Seen within the last 2 minutes.
  online: boolean
}

export interface QueueStatus {
  pending: number
  failed: number
}

export interface StatusResponse {
  // null before the first sync.
  last_sync: LastSync | null
  gmail: GmailStatus
  device: DeviceStatus
  queue: QueueStatus
  // Emails the classifier gave up on.
  failed_classifications: number
}

export interface SyncStarted {
  status: 'started'
}

export interface ConnectUrl {
  url: string
}

export interface DeviceCreated {
  id: string
  name: string
  // Shown only in this response.
  key: string
}

/** The body of every error response, whatever the status code. */
export interface ApiErrorBody {
  error: {
    code: string
    message: string
  }
}
