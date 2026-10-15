import { SyncButton } from '@/features/status/SyncButton'
import { PageTitle } from '@/shared/components/PageTitle'

// The mockup's Add manually button is left out of V1: there is no POST /applications.
export function Board() {
  return (
    <div className="px-6 py-6">
      <PageTitle title="Applications">
        <SyncButton />
      </PageTitle>
      <p className="mt-6 text-muted">Board placeholder.</p>
    </div>
  )
}
