import { useQuery } from '@tanstack/react-query'
import { getStatus } from '@/api/status'

/** Shared, so Sync now can invalidate it. */
export const statusQueryKey = ['status'] as const

export const STATUS_POLL_MS = 30_000

/** `GET /status`, polled every 30 seconds. TanStack pauses polling while the tab is hidden. */
export function useStatus() {
  return useQuery({
    queryKey: statusQueryKey,
    queryFn: getStatus,
    refetchInterval: STATUS_POLL_MS,
  })
}
