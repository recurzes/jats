import { adapt, getAuthClient } from '@/features/auth/neonAuth'

type NeonAuthClient = Parameters<typeof adapt>[0]

/** A JWT whose payload expires `secondsLeft` from now. Only `exp` is read. */
function jwt(secondsLeft: number, id = 'a') {
  const payload = btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + secondsLeft, id }))
  return `header.${payload}.signature`
}

function fakeNeon(
  session: { user: { id: string; email: string }; session: { token: string } } | null,
) {
  const neon = {
    getSession: vi.fn(async () => ({ data: session, error: null })),
    token: vi.fn(async () =>
      session ? { data: { token: jwt(900) }, error: null } : { data: null, error: { status: 401 } },
    ),
    signIn: { email: vi.fn(async () => ({ data: {}, error: null as { message: string } | null })) },
    signOut: vi.fn(async () => ({ data: {}, error: null })),
  }
  return { neon, auth: adapt(neon as unknown as NeonAuthClient) }
}

const signedIn = {
  user: { id: 'owner-id', email: 'me@example.com' },
  session: { token: 'opaque-session-id' },
}

test('creates one client from the config', () => {
  expect(getAuthClient()).toBe(getAuthClient())
})

test('getSession keeps only the user id and email', async () => {
  const { auth } = fakeNeon(signedIn)

  expect(await auth.getSession()).toEqual({ user: { id: 'owner-id', email: 'me@example.com' } })
})

test('getSession is null when signed out', async () => {
  const { auth } = fakeNeon(null)

  expect(await auth.getSession()).toBeNull()
})

test('getToken returns the JWT from token(), not the session id', async () => {
  const { neon, auth } = fakeNeon(signedIn)

  const token = await auth.getToken()

  expect(token).toMatch(/^header\./)
  expect(token).not.toBe('opaque-session-id')
  expect(neon.token).toHaveBeenCalledOnce()
})

test('getToken is null when signed out or unreachable', async () => {
  expect(await fakeNeon(null).auth.getToken()).toBeNull()

  const { neon, auth } = fakeNeon(signedIn)
  neon.token.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  expect(await auth.getToken()).toBeNull()
})

test('getToken reuses the token until a minute before it expires', async () => {
  const { neon, auth } = fakeNeon(signedIn)
  neon.token.mockResolvedValueOnce({ data: { token: jwt(900, 'first') }, error: null })

  const first = await auth.getToken()
  expect(await auth.getToken()).toBe(first)
  expect(neon.token).toHaveBeenCalledOnce()

  neon.token.mockResolvedValueOnce({ data: { token: jwt(30, 'nearly-expired') }, error: null })
  await auth.signOut()
  const nearlyExpired = await auth.getToken()
  expect(await auth.getToken()).not.toBe(nearlyExpired)
  expect(neon.token).toHaveBeenCalledTimes(3)
})

test('signIn passes the email and password, and is false on an error', async () => {
  const { neon, auth } = fakeNeon(null)

  expect(await auth.signIn('me@example.com', 'pw')).toBe(true)
  expect(neon.signIn.email).toHaveBeenCalledWith({ email: 'me@example.com', password: 'pw' })

  neon.signIn.email.mockResolvedValueOnce({ data: {}, error: { message: 'Invalid' } })
  expect(await auth.signIn('me@example.com', 'wrong')).toBe(false)
})
