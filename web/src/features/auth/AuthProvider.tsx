import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { setAuthFailureHandler, setTokenGetter } from '@/api/client'
import { getAuthClient, type AuthClient, type Session } from '@/features/auth/neonAuth'
import { SessionContext, type SessionContextValue } from '@/features/auth/useSession'

export const SESSION_EXPIRED = 'Session expired'
export const NOT_OWNER = 'This account does not have access to Jats.'

export function AuthProvider({
  children,
  auth = getAuthClient(),
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
    auth
      .getSession()
      .catch(() => null)
      .then((initial) => {
        if (!active) return
        setSession(initial)
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [auth])

  const endSession = useCallback(
    async (reason: string | null) => {
      setNotice(reason)
      // Offline: still forget the session on this device.
      await auth.signOut().catch(() => undefined)
      setSession(null)
      // The next login starts with an empty cache.
      queryClient.clear()
    },
    [auth, queryClient],
  )

  useEffect(() => {
    // Read at request time, not a stale copy: the token lasts 15 minutes.
    setTokenGetter(() => auth.getToken())
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
        if (!(await auth.signIn(email, password))) return false
        const next = await auth.getSession()
        if (!next) return false
        setSession(next)
        setNotice(null)
        return true
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
