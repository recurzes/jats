import { createBrowserRouter, type RouteObject } from 'react-router'
import { Login } from '@/features/auth/Login'
import { Board } from '@/features/board/Board'
import { AppShell } from '@/shared/components/AppShell'

// /settings arrives in branch 74 and the 404 route in branch 81.
export const routes: RouteObject[] = [
  { path: '/login', element: <Login /> },
  {
    element: <AppShell />,
    children: [{ index: true, element: <Board /> }],
  },
]

export function createRouter() {
  return createBrowserRouter(routes)
}
