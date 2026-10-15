import { Outlet } from 'react-router'
import { AppHeader } from '@/shared/components/AppHeader'

export function AppShell() {
  return (
    <div className="min-h-dvh bg-ground">
      <AppHeader />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
