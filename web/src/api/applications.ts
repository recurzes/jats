import { apiRequest } from '@/api/client'
import type {
  ApplicationDetail,
  ApplicationFilters,
  ApplicationPatch,
  ApplicationSummary,
  ReprintQueued,
} from '@/api/types'

export function getApplications(filters: ApplicationFilters = {}) {
  return apiRequest<ApplicationSummary[]>('/applications', { query: { ...filters } })
}

export function getApplication(id: string) {
  return apiRequest<ApplicationDetail>(`/applications/${encodeURIComponent(id)}`)
}

export function patchApplication(id: string, body: ApplicationPatch) {
  return apiRequest<ApplicationDetail>(`/applications/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body,
  })
}

/** 409 `REPRINT_PENDING` while an earlier reprint is still waiting to print. */
export function reprintApplication(id: string) {
  return apiRequest<ReprintQueued>(`/applications/${encodeURIComponent(id)}/reprint`, {
    method: 'POST',
  })
}
