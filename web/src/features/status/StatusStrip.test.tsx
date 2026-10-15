import type { ReactNode } from 'react'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import type { StatusResponse } from '@/api/types'
import { config } from '@/config'
import { StatusStrip } from '@/features/status/StatusStrip'
import { db } from '@/mocks/db'
import { createQueryClient } from '@/queryClient'
import { server } from '@/test/server'

const NOW = new Date('2026-10-14T12:00:00Z')
const minutesAgo = (minutes: number) => new Date(NOW.getTime() - minutes * 60_000).toISOString()

beforeEach(() => {
  // Only Date, so MSW and Testing Library keep their real timers.
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
})
afterEach(() => vi.useRealTimers())

function Wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createQueryClient()}>{children}</QueryClientProvider>
}

function renderStrip(changes: Partial<StatusResponse> = {}) {
  Object.assign(db.status, changes)
  render(<StatusStrip />, { wrapper: Wrapper })
  return screen.findByRole('list', { name: 'System status' })
}

const lastSync = (changes: Partial<NonNullable<StatusResponse['last_sync']>>) => ({
  started_at: minutesAgo(2),
  finished_at: minutesAgo(2),
  result: 'ok' as const,
  trigger: 'schedule' as const,
  error: null,
  ...changes,
})

describe('Gmail', () => {
  test('ok shows when it last synced', async () => {
    const strip = await renderStrip({ last_sync: lastSync({}) })
    expect(within(strip).getByText('Gmail synced 2 minutes ago')).toHaveAttribute(
      'data-tone',
      'good',
    )
  })

  test.each(['fallback_full', 'skipped_locked'] as const)('%s counts as good', async (result) => {
    const strip = await renderStrip({ last_sync: lastSync({ result }) })
    expect(within(strip).getByText('Gmail synced 2 minutes ago')).toHaveAttribute(
      'data-tone',
      'good',
    )
  })

  test('error uses the error tone', async () => {
    const strip = await renderStrip({ last_sync: lastSync({ result: 'error', error: 'boom' }) })
    expect(within(strip).getByText('Gmail sync failed 2 minutes ago')).toHaveAttribute(
      'data-tone',
      'error',
    )
  })

  test('a running sync uses started_at', async () => {
    const running = lastSync({ started_at: minutesAgo(1), finished_at: null, result: null })
    const strip = await renderStrip({ last_sync: running })
    expect(within(strip).getByText('Gmail sync started 1 minute ago')).toBeInTheDocument()
  })

  test('no sync yet', async () => {
    const strip = await renderStrip({ last_sync: null })
    expect(within(strip).getByText('Gmail not synced yet')).toHaveAttribute('data-tone', 'warning')
  })
})

describe('Printer', () => {
  test('online, with when it was last seen in a tooltip that opens on focus', async () => {
    const strip = await renderStrip({ device: { last_seen_at: minutesAgo(1), online: true } })
    const pill = within(strip).getByText('Printer online')
    expect(pill).toHaveAttribute('data-tone', 'good')

    await userEvent.tab()
    expect(pill).toHaveFocus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Last seen 1 minute ago')
  })

  test('offline', async () => {
    const strip = await renderStrip({ device: { last_seen_at: minutesAgo(60), online: false } })
    expect(within(strip).getByText('Printer offline')).toHaveAttribute('data-tone', 'error')
  })

  test('no device has ever polled', async () => {
    const strip = await renderStrip({ device: { last_seen_at: null, online: false } })
    expect(within(strip).getByText('Printer: never seen')).toHaveAttribute('data-tone', 'warning')
  })
})

describe('Print queue', () => {
  test('empty', async () => {
    const strip = await renderStrip({ queue: { pending: 0, failed: 0 } })
    expect(within(strip).getByText('Print queue: 0')).toHaveAttribute('data-tone', 'good')
  })

  test('some pending', async () => {
    const strip = await renderStrip({ queue: { pending: 3, failed: 0 } })
    expect(within(strip).getByText('Print queue: 3')).toHaveAttribute('data-tone', 'good')
  })

  test('some failed', async () => {
    const strip = await renderStrip({ queue: { pending: 2, failed: 1 } })
    expect(within(strip).getByText('Print queue: 2, 1 failed')).toHaveAttribute(
      'data-tone',
      'warning',
    )
  })
})

test('shows an error pill when /status cannot be read', async () => {
  server.use(http.get(`${config.apiUrl}/status`, () => HttpResponse.error()))
  render(<StatusStrip />, { wrapper: Wrapper })

  // The query client retries once, about a second later.
  expect(await screen.findByText('Status unavailable', {}, { timeout: 3000 })).toHaveAttribute(
    'data-tone',
    'error',
  )
})
