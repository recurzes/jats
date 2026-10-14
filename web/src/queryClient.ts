import { QueryClient } from '@tanstack/react-query'

/** Tests call this to get a fresh client per test. */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        staleTime: 10_000,
      },
    },
  })
}

export const queryClient = createQueryClient()
