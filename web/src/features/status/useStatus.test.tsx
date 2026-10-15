import type { ReactNode } from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { status } from '@/mocks/fixtures'
import { createQueryClient } from '@/queryClient'
import { STATUS_POLL_MS, statusQueryKey, useStatus } from '@/features/status/useStatus'

function renderUseStatus() {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, ...renderHook(() => useStatus(), { wrapper }) }
}

test('reads GET /status', async () => {
  const { result } = renderUseStatus()

  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(result.current.data).toEqual(status)
})

test('polls every 30 seconds under the shared key', async () => {
  const { queryClient, result } = renderUseStatus()
  await waitFor(() => expect(result.current.isSuccess).toBe(true))

  const query = queryClient.getQueryCache().find({ queryKey: statusQueryKey })
  expect(STATUS_POLL_MS).toBe(30_000)
  expect(query?.observers[0]?.options.refetchInterval).toBe(STATUS_POLL_MS)
})
