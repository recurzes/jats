import { Outlet } from 'react-router'

export function AppShell() {
  return (
    <div className="min-h-dvh bg-ground">
      {/* The header content arrives in branch 26 (feat/app-header). */}
      <header className="h-14 border-b bg-surface" />
      <main>
        <Outlet />
      </main>
    </div>
  )
}
