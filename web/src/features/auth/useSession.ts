import { createContext, useContext } from 'react'
import type { Session } from '@supabase/supabase-js'

export interface SessionContextValue {
  session: Session | null
  /** True until the stored session has been read. Never redirect while this is true. */
  loading: boolean
  /** Why the last session ended, when the app ended it ("Session expired"). */
  notice: string | null
  /** Resolves to false on any failure, so the form never says which part was wrong. */
  signIn: (email: string, password: string) => Promise<boolean>
  signOut: () => Promise<void>
}

export const SessionContext = createContext<SessionContextValue | null>(null)

export function useSession() {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside <AuthProvider>')
  return value
}
