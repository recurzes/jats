import type { ReactNode } from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { config } from '@/config'
import { applicationQueryKey, useApplicationDetail } from '@/features/detail/useApplicationDetail'
import { applicationDetail } from '@/mocks/fixtures'
import { createQueryClient } from '@/queryClient'
import { server } from '@/test/server'

function renderUseApplicationDetail(id: string | null) {
  const queryClient = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, ...renderHook(() => useApplicationDetail(id), { wrapper }) }
}

function countRequests() {
  const urls: string[] = []
  server.events.on('request:start', ({ request }) => urls.push(request.url))
  return urls
}

afterEach(() => server.events.removeAllListeners())

test('loads GET /applications/{id} under ["application", id]', async () => {
  const { queryClient, result } = renderUseApplicationDetail(applicationDetail.id)

  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(result.current.data).toEqual(applicationDetail)
  expect(queryClient.getQueryData(['application', applicationDetail.id])).toEqual(applicationDetail)
  expect(applicationQueryKey('x')).toEqual(['application', 'x'])
})

test('makes no request without an id', async () => {
  const urls = countRequests()
  const { result } = renderUseApplicationDetail(null)

  // Give a disabled query the chance to fire anyway.
  await new Promise((resolve) => setTimeout(resolve, 20))
  expect(result.current.fetchStatus).toBe('idle')
  expect(urls).toEqual([])
})

test('does not retry a 404', async () => {
  const urls = countRequests()
  const { result } = renderUseApplicationDetail('missing')

  await waitFor(() => expect(result.current.isError).toBe(true))
  expect(result.current.error).toMatchObject({ code: 'NOT_FOUND', status: 404 })
  expect(urls).toHaveLength(1)
})

test('retries other errors once', async () => {
  server.use(
    http.get(`${config.apiUrl}/applications/:id`, () =>
      HttpResponse.json({ error: { code: 'INTERNAL', message: 'Boom' } }, { status: 500 }),
    ),
  )
  const urls = countRequests()
  const { result } = renderUseApplicationDetail(applicationDetail.id)

  await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 3000 })
  expect(urls).toHaveLength(2)
})
