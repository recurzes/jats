import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { config } from '@/config'
import { applicationDetail } from '@/mocks/fixtures'
import { server } from '@/test/server'
import { renderRoutes } from '@/test/renderRoutes'

const detailUrl = `${config.apiUrl}/applications/:id`

function failDetail() {
  server.use(
    http.get(detailUrl, () =>
      HttpResponse.json({ error: { code: 'INTERNAL', message: 'Database down' } }, { status: 500 }),
    ),
  )
}

const openPanel = () => `/?app=${applicationDetail.id}`

test('closed without ?app=', async () => {
  renderRoutes('/')
  await screen.findByRole('heading', { name: 'Northwind Labs' })

  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

test('skeleton while loading, then the header', async () => {
  renderRoutes(openPanel())

  const dialog = await screen.findByRole('dialog')
  expect(dialog.querySelector('[aria-busy="true"]')).not.toBeNull()
  expect(dialog.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)

  expect(await screen.findByRole('dialog', { name: 'Northwind Labs' })).toBeInTheDocument()
  expect(dialog.querySelector('[data-slot="skeleton"]')).toBeNull()
})

test('header shows company, role, status and a close button', async () => {
  renderRoutes(openPanel())

  const dialog = await screen.findByRole('dialog', { name: 'Northwind Labs' })
  expect(dialog).toHaveAccessibleDescription('Frontend Engineer')
  expect(within(dialog).getByText('Replied', { selector: 'header *' })).toBeInTheDocument()
  expect(within(dialog).getByRole('button', { name: 'Close panel' })).toBeInTheDocument()
})

test('body shows the status history and the emails', async () => {
  renderRoutes(openPanel())

  const dialog = await screen.findByRole('dialog', { name: 'Northwind Labs' })
  expect(within(dialog).getByText('Acknowledged to Replied')).toBeInTheDocument()
  expect(within(dialog).getByText('Started as Acknowledged')).toBeInTheDocument()
  expect(within(dialog).getAllByRole('article')).toHaveLength(3)
})

test('footer holds the status select and Reprint, disabled for now', async () => {
  renderRoutes(openPanel())

  const dialog = await screen.findByRole('dialog', { name: 'Northwind Labs' })
  const select = within(dialog).getByLabelText('Wrong status? Change it')
  expect(select).toBeDisabled()
  expect(select).toHaveValue('replied')
  expect(within(dialog).getByRole('button', { name: 'Reprint receipt' })).toBeDisabled()
})

test('clicking a card opens its panel, and Close panel closes it', async () => {
  const { router } = renderRoutes('/')

  await userEvent.click(await screen.findByRole('button', { name: 'Northwind Labs' }))
  const dialog = await screen.findByRole('dialog', { name: 'Northwind Labs' })
  expect(router.state.location.search).toBe(`?app=${applicationDetail.id}`)

  await userEvent.click(within(dialog).getByRole('button', { name: 'Close panel' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(router.state.location.search).toBe('')
})

test('Escape closes the panel', async () => {
  const { router } = renderRoutes(openPanel())
  await screen.findByRole('dialog', { name: 'Northwind Labs' })

  await userEvent.keyboard('{Escape}')

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(router.state.location.search).toBe('')
})

test('a 404 shows "Application not found" with a close button', async () => {
  const { router } = renderRoutes('/?app=missing')

  const dialog = await screen.findByRole('dialog', { name: 'Application not found' })
  await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))

  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(router.state.location.search).toBe('')
})

test('other errors show the message, and Retry loads the panel', async () => {
  failDetail()
  renderRoutes(openPanel())

  const alert = await screen.findByRole('alert', {}, { timeout: 3000 })
  expect(alert).toHaveTextContent('Database down')

  server.resetHandlers()
  await userEvent.click(within(alert).getByRole('button', { name: 'Retry' }))

  expect(await screen.findByRole('dialog', { name: 'Northwind Labs' })).toBeInTheDocument()
})
