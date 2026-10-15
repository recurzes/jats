import { useQuery } from '@tanstack/react-query'
import { getApplication } from '@/api/applications'
import { ApiError } from '@/api/client'

export const applicationQueryKey = (id: string) => ['application', id] as const

export function isNotFound(error: unknown) {
  return error instanceof ApiError && error.code === 'NOT_FOUND'
}

/** `GET /applications/{id}`, only while a panel is open. A 404 is final, so it is not retried. */
export function useApplicationDetail(id: string | null) {
  return useQuery({
    queryKey: applicationQueryKey(id ?? ''),
    queryFn: () => getApplication(id!),
    enabled: !!id,
    retry: (failureCount, error) => !isNotFound(error) && failureCount < 1,
  })
}
