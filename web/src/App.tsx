import { useState } from 'react'
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { RouterProvider } from 'react-router'
import { AuthProvider } from '@/features/auth/AuthProvider'
import type { AuthClient } from '@/features/auth/supabase'
import { queryClient as defaultQueryClient } from '@/queryClient'
import { createRouter } from '@/router'

export default function App({
  queryClient = defaultQueryClient,
  auth,
}: {
  queryClient?: QueryClient
  auth?: AuthClient
}) {
  const [router] = useState(createRouter)

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider auth={auth}>
        <RouterProvider router={router} />
      </AuthProvider>
      {import.meta.env.DEV && <ReactQueryDevtools />}
    </QueryClientProvider>
  )
}
