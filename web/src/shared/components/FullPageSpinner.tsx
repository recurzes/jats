import { LoaderCircle } from 'lucide-react'

export function FullPageSpinner() {
  return (
    <div role="status" className="grid min-h-dvh place-items-center bg-ground">
      <LoaderCircle aria-hidden="true" className="size-6 animate-spin text-muted" />
      <span className="sr-only">Loading</span>
    </div>
  )
}
