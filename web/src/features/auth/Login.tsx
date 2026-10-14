import { useState, type FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router'
import type { LoginState } from '@/features/auth/ProtectedRoute'
import { useSession } from '@/features/auth/useSession'
import { FullPageSpinner } from '@/shared/components/FullPageSpinner'
import { Button } from '@/shared/components/ui/button'
import { Input } from '@/shared/components/ui/input'
import { Label } from '@/shared/components/ui/label'

// One message for every failure, so the form never reveals which part was wrong.
const LOGIN_FAILED = 'Wrong email or password'

export function Login() {
  const { session, loading } = useSession()

  if (loading) return <FullPageSpinner />
  // Also how a successful login reaches the board: the new session lands here.
  if (session) return <Navigate to="/" replace />
  return <LoginForm />
}

function LoginForm() {
  const { signIn } = useSession()
  const notice = (useLocation().state as LoginState | null)?.notice
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setPending(true)
    setError(null)
    const ok = await signIn(String(form.get('email')), String(form.get('password')))
    // On success the button stays disabled until the redirect.
    if (!ok) {
      setError(LOGIN_FAILED)
      setPending(false)
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center bg-ground px-4">
      <div className="w-full max-w-sm rounded-xl border bg-surface p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Log in to Jats</h1>
        {notice && !error && (
          <p
            role="status"
            className="mt-4 rounded-md border border-review-border bg-review-fill px-3 py-2 text-review-text"
          >
            {notice}
          </p>
        )}
        <form className="mt-6 grid gap-4" onSubmit={handleSubmit}>
          <div className="grid gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              aria-invalid={error ? true : undefined}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              aria-invalid={error ? true : undefined}
            />
          </div>
          {error && (
            <p role="alert" className="text-error">
              {error}
            </p>
          )}
          <Button type="submit" disabled={pending}>
            {pending ? 'Logging in…' : 'Log in'}
          </Button>
        </form>
      </div>
    </main>
  )
}
