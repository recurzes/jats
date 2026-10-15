import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { toast } from 'sonner'
import { startSync } from '@/api/gmail'
import { applicationsQueryKey } from '@/features/board/useApplications'
import { statusQueryKey } from '@/features/status/useStatus'
import { Button } from '@/shared/components/ui/button'

/** POST /sync answers 202 at once and syncs in the background, so refetch after this long. */
export const SYNC_REFETCH_DELAY_MS = 5_000

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** Runs a Gmail sync now instead of waiting up to 5 minutes for the scheduler. */
export function SyncButton() {
  const queryClient = useQueryClient()
  const sync = useMutation({
    mutationFn: startSync,
    // The mutation stays pending until this resolves, so the button stays disabled meanwhile.
    onSuccess: async () => {
      toast.success('Sync started')
      await wait(SYNC_REFETCH_DELAY_MS)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: statusQueryKey }),
        queryClient.invalidateQueries({ queryKey: applicationsQueryKey }),
      ])
    },
    // 409 GMAIL_NOT_CONNECTED or GMAIL_NEEDS_REAUTH. Branch 80 maps codes to friendlier text.
    onError: (error) => toast.error(error.message),
  })

  return (
    <Button variant="outline" disabled={sync.isPending} onClick={() => sync.mutate()}>
      <RefreshCw aria-hidden className={sync.isPending ? 'animate-spin' : undefined} />
      {sync.isPending ? 'Syncing…' : 'Sync now'}
    </Button>
  )
}
