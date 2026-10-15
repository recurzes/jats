import { screen, within } from '@testing-library/react'
import { renderRoutes } from '@/test/renderRoutes'

test('the header shows the wordmark, tagline, status strip and Sign out', async () => {
  renderRoutes('/')

  const header = await screen.findByRole('banner')
  expect(within(header).getByText('Jats')).toHaveClass('font-mono')
  expect(within(header).getByText('Job application tracker')).toBeInTheDocument()
  expect(await within(header).findByRole('list', { name: 'System status' })).toBeInTheDocument()
  expect(within(header).getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
})

test('the printer icon is hidden from screen readers', async () => {
  renderRoutes('/')

  const header = await screen.findByRole('banner')
  expect(header.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
})
