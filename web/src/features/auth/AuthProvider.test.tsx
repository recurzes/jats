import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { apiRequest } from '@/api/client'
import { AuthProvider, NOT_OWNER, SESSION_EXPIRED } from '@/features/auth/AuthProvider'
import type { Session } from '@/features/auth/neonAuth'
import { useSession } from '@/features/auth/useSession'
import { createQueryClient } from '@/queryClient'
import { createFakeAuth, fakeSession, PASSWORD } from '@/test/fakeAuth'
import { server } from '@/test/server'

const url = 'http://api.test/thing'

function renderProvider(fake = createFakeAuth(fakeSession())) {
  const queryClient = createQueryClient()

  function Probe() {
    const { session, loading, notice, signIn, signOut } = useSession()
    if (loading) return <p>loading</p>
    return (
      <>
        <p>
          user: {session?.user.email ?? 'none'}
          {notice && ` (${notice})`}
        </p>
        <button onClick={() => void signIn('me@example.com', PASSWORD)}>Sign in</button>
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
  fake.mock.getSession.mockImplementationOnce(() => new Promise((done) => (resolve = done)))
  renderProvider(fake)

  expect(screen.getByText('loading')).toBeInTheDocument()
  act(() => resolve(fakeSession('stored@example.com')))

  expect(await screen.findByText('user: stored@example.com')).toBeInTheDocument()
})

test('a failed session read counts as signed out', async () => {
  const fake = createFakeAuth()
  fake.mock.getSession.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  renderProvider(fake)

  expect(await screen.findByText('user: none')).toBeInTheDocument()
})

test('signing in sets the session', async () => {
  renderProvider(createFakeAuth())
  await screen.findByText('user: none')

  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByText('user: me@example.com')).toBeInTheDocument()
})

test('signOut ends the session and clears cached data', async () => {
  const { mock, queryClient } = renderProvider()
  await screen.findByText('user: me@example.com')
  queryClient.setQueryData(['applications'], [])

  await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

  expect(await screen.findByText('user: none')).toBeInTheDocument()
  expect(queryClient.getQueryData(['applications'])).toBeUndefined()
  expect(mock.signOut).toHaveBeenCalled()
})

test('signOut still forgets the session when offline', async () => {
  const fake = createFakeAuth(fakeSession())
  fake.mock.signOut.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  renderProvider(fake)
  await screen.findByText('user: me@example.com')

  await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

  expect(await screen.findByText('user: none')).toBeInTheDocument()
})

test('API requests carry the current access token', async () => {
  const seen: (string | null)[] = []
  server.use(
    http.get(url, ({ request }) => {
      seen.push(request.headers.get('Authorization'))
      return HttpResponse.json({})
    }),
  )
  const { setToken } = renderProvider()
  await screen.findByText('user: me@example.com')

  await apiRequest('/thing')
  // The token was refreshed: the next request sends the new one.
  setToken('refreshed-token')
  await apiRequest('/thing')

  expect(seen).toEqual(['Bearer test-access-token', 'Bearer refreshed-token'])
})

test('a 401 signs out with "Session expired"', async () => {
  failWith(401, 'AUTH_INVALID')
  const { mock } = renderProvider()
  await screen.findByText('user: me@example.com')

  await expect(apiRequest('/thing')).rejects.toMatchObject({ status: 401 })

  expect(await screen.findByText(`user: none (${SESSION_EXPIRED})`)).toBeInTheDocument()
  expect(mock.signOut).toHaveBeenCalled()
})

test('a 403 NOT_OWNER signs out instead of retrying', async () => {
  failWith(403, 'NOT_OWNER')
  renderProvider()
  await screen.findByText('user: me@example.com')

  await expect(apiRequest('/thing')).rejects.toMatchObject({ code: 'NOT_OWNER' })

  expect(await screen.findByText(`user: none (${NOT_OWNER})`)).toBeInTheDocument()
})

test('logging in again clears the notice', async () => {
  failWith(401, 'AUTH_INVALID')
  renderProvider()
  await screen.findByText('user: me@example.com')
  await apiRequest('/thing').catch(() => undefined)
  await screen.findByText(`user: none (${SESSION_EXPIRED})`)

  await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  expect(await screen.findByText('user: me@example.com')).toBeInTheDocument()
})
