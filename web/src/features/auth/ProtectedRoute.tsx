import type { ReactNode } from 'react'
import { Navigate } from 'react-router'
import { useSession } from '@/features/auth/useSession'
import { FullPageSpinner } from '@/shared/components/FullPageSpinner'

/** What `/login` reads from router state, to say why you were sent there. */
export interface LoginState {
  notice?: string
}

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, loading, notice } = useSession()

  // Redirecting now would bounce a refresh to /login before the stored session is read.
  if (loading) return <FullPageSpinner />
  if (!session) {
    const state: LoginState | undefined = notice ? { notice } : undefined
    return <Navigate to="/login" replace state={state} />
  }
  return children
}
