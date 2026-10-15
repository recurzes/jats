import { Printer } from 'lucide-react'
import { useSession } from '@/features/auth/useSession'
import { StatusStrip } from '@/features/status/StatusStrip'
import { Button } from '@/shared/components/ui/button'

/** Wordmark on the left; the status strip on the right, so problems show without a click. */
export function AppHeader() {
  const { signOut } = useSession()

  return (
    <header className="border-b bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-6 py-3">
        <div className="flex items-center gap-2.5">
          {/* The wordmark carries the name. */}
          <Printer aria-hidden className="size-5 text-accent" />
          <span className="font-mono text-lg font-semibold">Jats</span>
          <span className="text-muted">Job application tracker</span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <StatusStrip />
          <Button variant="ghost" size="sm" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </div>
    </header>
  )
}
