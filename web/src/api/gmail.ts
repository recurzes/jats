import { apiRequest } from '@/api/client'
import type { ConnectUrl, SyncStarted } from '@/api/types'

export function getGmailConnectUrl() {
  return apiRequest<ConnectUrl>('/auth/google/start')
}

/** Lives in the backend's Gmail router. 409 `GMAIL_NOT_CONNECTED` or `GMAIL_NEEDS_REAUTH`. */
export function startSync() {
  return apiRequest<SyncStarted>('/sync', { method: 'POST' })
}
