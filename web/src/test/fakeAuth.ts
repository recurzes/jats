import type { AuthClient, Session } from '@/features/auth/neonAuth'

/** The only password the fake accepts. */
export const PASSWORD = 'correct horse'

export const ACCESS_TOKEN = 'test-access-token'

export function fakeSession(email = 'me@example.com'): Session {
  return { user: { id: 'owner-id', email } }
}

/** An in-memory auth client. `mock` exposes the spies; `setToken` swaps the token it hands out. */
export function createFakeAuth(initial: Session | null = null) {
  let current = initial
  let token = ACCESS_TOKEN

  const mock = {
    getSession: vi.fn(async (): Promise<Session | null> => current),
    signIn: vi.fn(async (email: string, password: string) => {
      if (password !== PASSWORD) return false
      current = fakeSession(email)
      return true
    }),
    signOut: vi.fn(async () => {
      current = null
    }),
    getToken: vi.fn(async () => (current ? token : null)),
  }

  function setToken(next: string) {
    token = next
  }

  return { auth: mock satisfies AuthClient as AuthClient, mock, setToken }
}
