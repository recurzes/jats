import { apiRequest } from '@/api/client'
import type { DeviceCreated } from '@/api/types'

/** The key is only in this response; it cannot be read again. */
export function createDevice(name: string) {
  return apiRequest<DeviceCreated>('/devices', { method: 'POST', body: { name } })
}
