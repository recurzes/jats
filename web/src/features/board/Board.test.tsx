import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { config } from '@/config'
import { Board } from '@/features/board/Board'
import { applicationsQueryKey } from '@/features/board/useApplications'
import { db } from '@/mocks/db'
import { server } from '@/test/server'

const applicationsUrl = `${config.apiUrl}/applications`

function failApplications() {
  server.use(
    http.get(applicationsUrl, () =>
      HttpResponse.json({ error: { code: 'INTERNAL', message: 'Database down' } }, { status: 500 }),
    ),
  )
}

function renderBoard() {
  // No retries, so failures show at once.
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const { container } = render(
    <QueryClientProvider client={queryClient}>
      <Board />
    </QueryClientProvider>,
  )
  return { container, queryClient }
}

const column = (name: string) => screen.getByRole('region', { name: new RegExp(`^${name}`) })

test('four columns in order, each with its count and cards', async () => {
  renderBoard()
  await screen.findByRole('heading', { name: 'Northwind Labs' })

  const regions = screen.getAllByRole('region')
  expect(regions.map((region) => region.querySelector('h2')?.textContent)).toEqual([
    'Acknowledged3',
    'Replied2',
    'Update2',
    'Rejected2',
  ])
  const replied = within(column('Replied')).getAllByRole('listitem')
  // Newest first.
  expect(replied.map((item) => within(item).getByRole('heading').textContent)).toEqual([
    'Northwind Labs',
    'Stackhouse',
  ])
})

test('shows "9 tracked" next to the title once loaded', async () => {
  renderBoard()

  expect(screen.queryByText(/tracked/)).not.toBeInTheDocument()
  expect(await screen.findByText('9 tracked')).toHaveClass('font-mono')
})

test('skeleton cards in a busy region during the first load, then cards', async () => {
  const { container } = renderBoard()

  const busy = container.querySelector('[aria-busy="true"]')
  expect(busy).not.toBeNull()
  expect(busy?.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  expect(screen.queryByRole('listitem')).not.toBeInTheDocument()

  await screen.findByRole('heading', { name: 'Northwind Labs' })
  expect(container.querySelector('[aria-busy="true"]')).toBeNull()
  expect(container.querySelector('[data-slot="skeleton"]')).toBeNull()
})

describe('empty states', () => {
  test('an empty column says so', async () => {
    db.applications = db.applications.filter((application) => application.status !== 'rejected')
    renderBoard()
    await screen.findByRole('heading', { name: 'Northwind Labs' })

    expect(within(column('Rejected')).getByText('Nothing here yet')).toBeInTheDocument()
    expect(within(column('Rejected')).queryByRole('list')).not.toBeInTheDocument()
  })

  test('an empty board shows a hint', async () => {
    db.applications = []
    renderBoard()

    expect(await screen.findByText('No applications yet')).toBeInTheDocument()
    expect(screen.getByText('0 tracked')).toBeInTheDocument()
  })
})

describe('errors', () => {
  test('a failed first load shows an error panel, and Retry loads the board', async () => {
    failApplications()
    renderBoard()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Database down')
    expect(screen.queryByText(/tracked/)).not.toBeInTheDocument()

    server.resetHandlers()
    await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await screen.findByRole('heading', { name: 'Northwind Labs' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  test('a failed refetch keeps the cards and notes it', async () => {
    const { queryClient } = renderBoard()
    await screen.findByRole('heading', { name: 'Northwind Labs' })

    failApplications()
    await act(() => queryClient.refetchQueries({ queryKey: applicationsQueryKey }))

    expect(await screen.findByRole('status')).toHaveTextContent("Couldn't refresh. Database down")
    expect(screen.getByRole('heading', { name: 'Northwind Labs' })).toBeInTheDocument()
    expect(screen.getByText('9 tracked')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
