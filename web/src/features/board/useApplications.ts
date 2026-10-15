import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { getApplications } from '@/api/applications'

/** Shared, so Sync now and the status mutations can update and invalidate it. */
export const applicationsQueryKey = ['applications'] as const

export const APPLICATIONS_POLL_MS = 30_000

/** `GET /applications`, polled every 30 seconds. Old data stays on screen while it refetches. */
export function useApplications() {
  return useQuery({
    queryKey: applicationsQueryKey,
    queryFn: () => getApplications(),
    refetchInterval: APPLICATIONS_POLL_MS,
    placeholderData: keepPreviousData,
  })
}
