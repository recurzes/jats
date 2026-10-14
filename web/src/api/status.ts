import { apiRequest } from '@/api/client'
import type { StatusResponse } from '@/api/types'

export function getStatus() {
  return apiRequest<StatusResponse>('/status')
}
