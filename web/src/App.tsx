import { useState } from 'react'
import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { RouterProvider } from 'react-router'
import { queryClient as defaultQueryClient } from '@/queryClient'
import { createRouter } from '@/router'

export default function App({ queryClient = defaultQueryClient }: { queryClient?: QueryClient }) {
  const [router] = useState(createRouter)

  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      {import.meta.env.DEV && <ReactQueryDevtools />}
    </QueryClientProvider>
  )
}
