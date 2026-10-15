import { Button } from '@/shared/components/ui/button'

// Branch 80 maps error codes to friendlier sentences. Until then, show the API's message.

/** The first load failed, so there is nothing to show. */
export function BoardError({
  message,
  retrying,
  onRetry,
}: {
  message: string
  retrying: boolean
  onRetry: () => void
}) {
  return (
    <div role="alert" className="rounded-xl border bg-surface p-6 text-center">
      <p className="font-semibold">Couldn't load your applications</p>
      <p className="mt-1 text-muted">{message}</p>
      <Button variant="outline" className="mt-4" disabled={retrying} onClick={onRetry}>
        {retrying ? 'Retrying…' : 'Retry'}
      </Button>
    </div>
  )
}

/** A background refetch failed. The last loaded cards stay on screen. */
export function RefreshFailed({ message }: { message: string }) {
  return (
    <p role="status" className="text-label text-muted">
      <span className="font-medium text-error">Couldn't refresh.</span> {message}
    </p>
  )
}

/** Replaced on a fresh account by the onboarding card in branch 73. */
export function EmptyBoard() {
  return (
    <div className="rounded-xl border border-dashed bg-surface p-6 text-center">
      <p className="font-semibold">No applications yet</p>
      <p className="mt-1 text-muted">
        When an application email arrives in Gmail, Jats adds it here after the next sync.
      </p>
    </div>
  )
}
