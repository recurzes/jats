import { Outlet } from 'react-router'
import { useSession } from '@/features/auth/useSession'
import { Button } from '@/shared/components/ui/button'

export function AppShell() {
  const { signOut } = useSession()

  return (
    <div className="min-h-dvh bg-ground">
      {/* The header content arrives in branch 26 (feat/app-header). */}
      <header className="flex h-14 items-center justify-end border-b bg-surface px-4">
        <Button variant="ghost" onClick={() => void signOut()}>
          Sign out
        </Button>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  )
}
