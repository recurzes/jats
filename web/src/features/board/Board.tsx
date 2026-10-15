import { useMemo } from 'react'
import type { ApplicationSummary } from '@/api/types'
import { BoardError, EmptyBoard, RefreshFailed } from '@/features/board/BoardStates'
import { Column } from '@/features/board/Column'
import { groupByStatus } from '@/features/board/groupByStatus'
import { useApplications } from '@/features/board/useApplications'
import { ApplicationPanel } from '@/features/detail/ApplicationPanel'
import { SyncButton } from '@/features/status/SyncButton'
import { PageTitle } from '@/shared/components/PageTitle'
import { STATUS_ORDER } from '@/shared/lib/statuses'

// Four columns at desktop width, one on a phone. min() keeps very narrow screens from scrolling.
const GRID = 'grid items-start gap-4 grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))]'

function Columns({ applications }: { applications?: ApplicationSummary[] }) {
  const columns = useMemo(() => applications && groupByStatus(applications), [applications])

  return (
    <div className={GRID} aria-busy={!columns}>
      {STATUS_ORDER.map((status) => (
        <Column key={status} status={status} applications={columns?.[status]} />
      ))}
    </div>
  )
}

function BoardBody() {
  const { data, error, isPending, isFetching, refetch } = useApplications()

  // Skeletons only on the first load. Background refetches keep the cards.
  if (isPending) return <Columns />
  if (!data) {
    return (
      <BoardError message={error.message} retrying={isFetching} onRetry={() => void refetch()} />
    )
  }
  return (
    <div className="flex flex-col gap-3">
      {error && <RefreshFailed message={error.message} />}
      {data.length === 0 ? <EmptyBoard /> : <Columns applications={data} />}
    </div>
  )
}

// The mockup's Add manually button is left out of V1: there is no POST /applications.
export function Board() {
  const { data } = useApplications()

  return (
    <div className="px-6 py-6">
      {/* Hidden until the first load finishes, rather than showing "0 tracked". */}
      <PageTitle title="Applications" meta={data && `${data.length} tracked`}>
        <SyncButton />
      </PageTitle>
      <div className="mt-6">
        <BoardBody />
      </div>
      <ApplicationPanel />
    </div>
  )
}
