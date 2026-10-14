import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'
import { useQueryClient } from '@tanstack/react-query'
import { setAuthFailureHandler, setTokenGetter } from '@/api/client'
import { getSupabase, type AuthClient } from '@/features/auth/supabase'
import { SessionContext, type SessionContextValue } from '@/features/auth/useSession'

export const SESSION_EXPIRED = 'Session expired'
export const NOT_OWNER = 'This account does not have access to Jats.'

export function AuthProvider({
  children,
  auth = getSupabase().auth,
}: {
  children: ReactNode
  auth?: AuthClient
}) {
  const queryClient = useQueryClient()
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let heardEvent = false
    const {
      data: { subscription },
    } = auth.onAuthStateChange((_event, next) => {
      heardEvent = true
      setSession(next)
      setLoading(false)
      if (next) setNotice(null)
    })
    auth
      .getSession()
      .then(
        ({ data }) => data.session,
        () => null,
      )
      .then((initial) => {
        // An event that arrived first is newer than this read.
        if (!active || heardEvent) return
        setSession(initial)
        setLoading(false)
      })
    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [auth])

  const endSession = useCallback(
    async (reason: string | null) => {
      setNotice(reason)
      // A forced sign-out stays local: the server already rejects the token.
      const { error } = await auth.signOut({ scope: reason ? 'local' : 'global' })
      // Offline: still forget the session on this device.
      if (error) await auth.signOut({ scope: 'local' })
      setSession(null)
      // The next login starts with an empty cache.
      queryClient.clear()
    },
    [auth, queryClient],
  )

  useEffect(() => {
    // Read at request time, not a stale copy: Supabase refreshes the token.
    setTokenGetter(async () => (await auth.getSession()).data.session?.access_token ?? null)
    // A 403 NOT_OWNER would fail the same way every time, so end the session instead of retrying.
    setAuthFailureHandler((error) => {
      void endSession(error.code === 'NOT_OWNER' ? NOT_OWNER : SESSION_EXPIRED)
    })
    return () => {
      setTokenGetter(() => null)
      setAuthFailureHandler(() => {})
    }
  }, [auth, endSession])

  const signIn = useCallback(
    async (email: string, password: string) => {
      try {
        const { error } = await auth.signInWithPassword({ email, password })
        return !error
      } catch {
        return false
      }
    },
    [auth],
  )

  const value = useMemo<SessionContextValue>(
    () => ({ session, loading, notice, signIn, signOut: () => endSession(null) }),
    [session, loading, notice, signIn, endSession],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
