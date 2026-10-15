import { useId, useState, type ReactNode } from 'react'
import { PrinterIcon, XIcon } from 'lucide-react'
import type { ApplicationDetail } from '@/api/types'
import { EmailList } from '@/features/detail/EmailList'
import { StatusHistory } from '@/features/detail/StatusHistory'
import { isNotFound, useApplicationDetail } from '@/features/detail/useApplicationDetail'
import { useSelectedApp } from '@/features/detail/useSelectedApp'
import { StatusDot } from '@/shared/components/StatusDot'
import { Button } from '@/shared/components/ui/button'
import { Label } from '@/shared/components/ui/label'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from '@/shared/components/ui/sheet'
import { Skeleton } from '@/shared/components/ui/skeleton'
import { STATUSES, STATUS_ORDER } from '@/shared/lib/statuses'

function CloseButton() {
  return (
    <SheetClose asChild>
      <Button variant="ghost" size="icon" aria-label="Close panel" className="-mt-2 -mr-2">
        <XIcon />
      </Button>
    </SheetClose>
  )
}

/** The header row every state shares: a title on the left, the close button on the right. */
function Header({ children }: { children: ReactNode }) {
  return (
    <header className="flex items-start gap-3 border-b px-5 pt-5 pb-4">
      <div className="min-w-0 flex-1">{children}</div>
      <CloseButton />
    </header>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-label font-semibold tracking-wide text-muted uppercase">{title}</h3>
      {children}
    </section>
  )
}

function StatusLabel({ status }: { status: ApplicationDetail['status'] }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border bg-surface px-2.5 py-1 text-label whitespace-nowrap">
      <StatusDot status={status} className="size-2" />
      {STATUSES[status].label}
    </span>
  )
}

/** Laid out now so the panel is final. The select is wired in branch 54, Reprint in branch 67. */
function Footer({ status }: { status: ApplicationDetail['status'] }) {
  const selectId = useId()

  return (
    <footer className="sticky bottom-0 flex flex-col gap-3 border-t bg-surface px-5 py-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor={selectId}>Wrong status? Change it</Label>
        <select
          id={selectId}
          value={status}
          disabled
          onChange={() => {}}
          className="h-11 w-full rounded-md border bg-surface px-3 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {STATUS_ORDER.map((option) => (
            <option key={option} value={option}>
              {STATUSES[option].label}
            </option>
          ))}
        </select>
      </div>
      <Button variant="outline" disabled>
        <PrinterIcon />
        Reprint receipt
      </Button>
    </footer>
  )
}

function Loaded({ application }: { application: ApplicationDetail }) {
  const { company, role, status, status_events, emails } = application

  return (
    <>
      <Header>
        <SheetTitle className="text-xl leading-tight break-words">{company}</SheetTitle>
        {role && <SheetDescription className="mt-1 break-words">{role}</SheetDescription>}
        <div className="mt-3">
          <StatusLabel status={status} />
        </div>
      </Header>
      <div className="flex flex-1 flex-col gap-6 overflow-y-auto px-5 py-5">
        <Section title="Status history">
          <StatusHistory events={status_events} />
        </Section>
        <Section title="Emails">
          <EmailList emails={emails} />
        </Section>
      </div>
      <Footer status={status} />
    </>
  )
}

function Loading() {
  return (
    <>
      <Header>
        <SheetTitle className="sr-only">Loading application</SheetTitle>
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="mt-2 h-4 w-1/2" />
        <Skeleton className="mt-3 h-6 w-28 rounded-full" />
      </Header>
      <div aria-busy className="flex flex-col gap-3 px-5 py-5">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="mt-3 h-4 w-1/4" />
        <Skeleton className="h-24 w-full" />
      </div>
    </>
  )
}

function NotFound() {
  return (
    <>
      <Header>
        <SheetTitle className="text-xl">Application not found</SheetTitle>
      </Header>
      <div className="flex flex-col items-start gap-4 px-5 py-5">
        <p className="text-muted">It may have been deleted, or the link is wrong.</p>
        <SheetClose asChild>
          <Button variant="outline">Close</Button>
        </SheetClose>
      </div>
    </>
  )
}

function LoadError({
  message,
  retrying,
  onRetry,
}: {
  message: string
  retrying: boolean
  onRetry: () => void
}) {
  return (
    <>
      <Header>
        <SheetTitle className="text-xl">Couldn't load this application</SheetTitle>
      </Header>
      <div role="alert" className="flex flex-col items-start gap-4 px-5 py-5">
        <p className="text-muted">{message}</p>
        <Button variant="outline" disabled={retrying} onClick={onRetry}>
          {retrying ? 'Retrying…' : 'Retry'}
        </Button>
      </div>
    </>
  )
}

function PanelBody({ id }: { id: string }) {
  const { data, error, isPending, isFetching, refetch } = useApplicationDetail(id)

  if (isPending) return <Loading />
  if (!data) {
    if (isNotFound(error)) return <NotFound />
    return (
      <LoadError message={error.message} retrying={isFetching} onRetry={() => void refetch()} />
    )
  }
  return <Loaded application={data} />
}

/** The side panel for `?app=<id>`. 520 px on desktop, full width on phones. */
export function ApplicationPanel() {
  const { id, close } = useSelectedApp()
  // Keep the last id while the panel slides out, so it does not go blank as it closes.
  const [shownId, setShownId] = useState(id)
  if (id && id !== shownId) setShownId(id)

  return (
    <Sheet open={!!id} onOpenChange={(open) => !open && close()}>
      <SheetContent showCloseButton={false} className="w-full gap-0 sm:max-w-[520px]">
        {shownId && <PanelBody id={shownId} />}
      </SheetContent>
    </Sheet>
  )
}
