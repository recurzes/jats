import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Session } from '@supabase/supabase-js'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { apiRequest } from '@/api/client'
import { AuthProvider, NOT_OWNER, SESSION_EXPIRED } from '@/features/auth/AuthProvider'
import { useSession } from '@/features/auth/useSession'
import { createQueryClient } from '@/queryClient'
import { createFakeAuth, fakeSession } from '@/test/fakeAuth'
import { server } from '@/test/server'

const url = 'http://api.test/thing'

function renderProvider(fake = createFakeAuth(fakeSession())) {
  const queryClient = createQueryClient()

  function Probe() {
    const { session, loading, notice, signOut } = useSession()
    if (loading) return <p>loading</p>
    return (
      <>
        <p>
          token: {session?.access_token ?? 'none'}
          {notice && ` (${notice})`}
        </p>
        <button onClick={() => void signOut()}>Sign out</button>
      </>
    )
  }

  const view = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider auth={fake.auth}>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return { ...fake, queryClient, view }
}

function failWith(status: number, code: string) {
  server.use(http.get(url, () => HttpResponse.json({ error: { code, message: code } }, { status })))
}

test('shows loading, then the stored session', async () => {
  const fake = createFakeAuth()
  let resolve!: (session: Session) => void
  fake.mock.getSession.mockImplementationOnce(
    () => new Promise((done) => (resolve = (session) => done({ data: { session }, error: null }))),
  )
  renderProvider(fake)

  expect(screen.getByText('loading')).toBeInTheDocument()
  act(() => resolve(fakeSession('stored-token')))

  expect(await screen.findByText('token: stored-token')).toBeInTheDocument()
})

test('follows auth changes and unsubscribes on unmount', async () => {
  const { emit, listeners, view } = renderProvider(createFakeAuth())
  await screen.findByText('token: none')

  act(() => emit('SIGNED_IN', fakeSession('new-token')))
  expect(screen.getByText('token: new-token')).toBeInTheDocument()

  view.unmount()
  expect(listeners.size).toBe(0)
})

test('signOut ends the session and clears cached data', async () => {
  const { mock, queryClient } = renderProvider()
  await screen.findByText('token: test-access-token')
  queryClient.setQueryData(['applications'], [])

  await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

  expect(await screen.findByText('token: none')).toBeInTheDocument()
  expect(queryClient.getQueryData(['applications'])).toBeUndefined()
  expect(mock.signOut).toHaveBeenCalledWith({ scope: 'global' })
})

test('API requests carry the current access token', async () => {
  const seen: (string | null)[] = []
  server.use(
    http.get(url, ({ request }) => {
      seen.push(request.headers.get('Authorization'))
      return HttpResponse.json({})
    }),
  )
  const { emit } = renderProvider()
  await screen.findByText('token: test-access-token')

  await apiRequest('/thing')
  // Supabase refreshed the token: the next request sends the new one.
  act(() => emit('TOKEN_REFRESHED', fakeSession('refreshed-token')))
  await apiRequest('/thing')

  expect(seen).toEqual(['Bearer test-access-token', 'Bearer refreshed-token'])
})

test('a 401 signs out with "Session expired"', async () => {
  failWith(401, 'AUTH_INVALID')
  const { mock } = renderProvider()
  await screen.findByText('token: test-access-token')

  await expect(apiRequest('/thing')).rejects.toMatchObject({ status: 401 })

  expect(await screen.findByText(`token: none (${SESSION_EXPIRED})`)).toBeInTheDocument()
  expect(mock.signOut).toHaveBeenCalledWith({ scope: 'local' })
})

test('a 403 NOT_OWNER signs out instead of retrying', async () => {
  failWith(403, 'NOT_OWNER')
  renderProvider()
  await screen.findByText('token: test-access-token')

  await expect(apiRequest('/thing')).rejects.toMatchObject({ code: 'NOT_OWNER' })

  expect(await screen.findByText(`token: none (${NOT_OWNER})`)).toBeInTheDocument()
})

test('logging in again clears the notice', async () => {
  failWith(401, 'AUTH_INVALID')
  const { emit } = renderProvider()
  await screen.findByText('token: test-access-token')
  await apiRequest('/thing').catch(() => undefined)
  await screen.findByText(`token: none (${SESSION_EXPIRED})`)

  act(() => emit('SIGNED_IN', fakeSession()))

  expect(screen.getByText('token: test-access-token')).toBeInTheDocument()
})
