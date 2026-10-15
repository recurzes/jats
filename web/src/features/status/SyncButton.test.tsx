import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { SYNC_REFETCH_DELAY_MS, SyncButton } from '@/features/status/SyncButton'
import { statusQueryKey } from '@/features/status/useStatus'
import { db } from '@/mocks/db'
import { createQueryClient } from '@/queryClient'
import { Toaster } from '@/shared/components/ui/sonner'

beforeEach(() => {
  // shouldAdvanceTime keeps real time moving, so MSW still answers.
  vi.useFakeTimers({ shouldAdvanceTime: true })
})
afterEach(() => vi.useRealTimers())

function renderButton() {
  const queryClient = createQueryClient()
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
  const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
  render(
    <QueryClientProvider client={queryClient}>
      <SyncButton />
      <Toaster />
    </QueryClientProvider>,
  )
  return { invalidate, user }
}

test('starts a sync, toasts, and refetches status and applications a few seconds later', async () => {
  const { invalidate, user } = renderButton()

  await user.click(screen.getByRole('button', { name: 'Sync now' }))

  expect(await screen.findByText('Sync started')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Syncing…' })).toBeDisabled()
  expect(db.status.last_sync?.trigger).toBe('manual')
  expect(invalidate).not.toHaveBeenCalled()

  await vi.advanceTimersByTimeAsync(SYNC_REFETCH_DELAY_MS)

  expect(invalidate).toHaveBeenCalledWith({ queryKey: statusQueryKey })
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ['applications'] })
  expect(await screen.findByRole('button', { name: 'Sync now' })).toBeEnabled()
})

test('a 409 toasts the message and enables the button again', async () => {
  db.status.gmail = { state: 'not_connected', address: null }
  const { invalidate, user } = renderButton()

  await user.click(screen.getByRole('button', { name: 'Sync now' }))

  expect(await screen.findByText('No Gmail account is connected')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Sync now' })).toBeEnabled()
  expect(invalidate).not.toHaveBeenCalled()
})
