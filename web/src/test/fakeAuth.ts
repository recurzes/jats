import type { AuthChangeEvent, Session } from '@supabase/supabase-js'
import type { AuthClient } from '@/features/auth/supabase'

/** The only password the fake accepts. */
export const PASSWORD = 'correct horse'

export function fakeSession(accessToken = 'test-access-token'): Session {
  return {
    access_token: accessToken,
    refresh_token: 'test-refresh-token',
    expires_in: 3600,
    token_type: 'bearer',
    user: { id: 'owner-id', email: 'me@example.com' },
  } as Session
}

type Listener = (event: AuthChangeEvent, session: Session | null) => void

/** An in-memory Supabase auth client. `mock` exposes the spies, `emit` fires auth events. */
export function createFakeAuth(initial: Session | null = null) {
  let current = initial
  const listeners = new Set<Listener>()

  function emit(event: AuthChangeEvent, next: Session | null) {
    current = next
    for (const listener of listeners) listener(event, next)
  }

  const mock = {
    getSession: vi.fn(async () => ({ data: { session: current }, error: null })),
    onAuthStateChange: vi.fn((listener: Listener) => {
      listeners.add(listener)
      const unsubscribe = vi.fn(() => void listeners.delete(listener))
      return { data: { subscription: { id: 'fake', callback: listener, unsubscribe } } }
    }),
    signInWithPassword: vi.fn(async ({ password }: { email: string; password: string }) => {
      if (password !== PASSWORD) {
        return {
          data: { user: null, session: null },
          error: new Error('Invalid login credentials'),
        }
      }
      const session = fakeSession()
      emit('SIGNED_IN', session)
      return { data: { user: session.user, session }, error: null }
    }),
    signOut: vi.fn(async (_options?: { scope?: string }) => {
      emit('SIGNED_OUT', null)
      return { error: null }
    }),
  }

  return { auth: mock as unknown as AuthClient, mock, emit, listeners }
}
