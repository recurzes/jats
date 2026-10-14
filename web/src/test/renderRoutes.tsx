import { render } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider, type InitialEntry } from 'react-router'
import { AuthProvider } from '@/features/auth/AuthProvider'
import type { AuthClient } from '@/features/auth/supabase'
import { createQueryClient } from '@/queryClient'
import { routes } from '@/router'
import { createFakeAuth, fakeSession } from '@/test/fakeAuth'

/** The app's routes at `entry`, logged in unless you pass another `auth`. */
export function renderRoutes(
  entry: InitialEntry,
  {
    auth = createFakeAuth(fakeSession()).auth,
    queryClient = createQueryClient(),
  }: { auth?: AuthClient; queryClient?: ReturnType<typeof createQueryClient> } = {},
) {
  const router = createMemoryRouter(routes, { initialEntries: [entry] })
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider auth={auth}>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
  return { router, queryClient }
}
