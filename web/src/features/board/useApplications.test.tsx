import type { ReactNode } from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import {
  APPLICATIONS_POLL_MS,
  applicationsQueryKey,
  useApplications,
} from '@/features/board/useApplications'
import { applications } from '@/mocks/fixtures'
import { createQueryClient } from '@/queryClient'

function renderUseApplications() {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, ...renderHook(() => useApplications(), { wrapper }) }
}

test('reads GET /applications', async () => {
  const { result } = renderUseApplications()

  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(result.current.data).toEqual(applications)
})

test('polls every 30 seconds under the shared key', async () => {
  const { queryClient, result } = renderUseApplications()
  await waitFor(() => expect(result.current.isSuccess).toBe(true))

  const query = queryClient.getQueryCache().find({ queryKey: applicationsQueryKey })
  expect(applicationsQueryKey).toEqual(['applications'])
  expect(APPLICATIONS_POLL_MS).toBe(30_000)
  expect(query?.observers[0]?.options.refetchInterval).toBe(APPLICATIONS_POLL_MS)
})
