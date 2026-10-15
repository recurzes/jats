import { render, screen } from '@testing-library/react'
import { PageTitle } from '@/shared/components/PageTitle'

test('renders the title as the h1 with its actions', () => {
  render(
    <PageTitle title="Applications">
      <button type="button">Sync now</button>
    </PageTitle>,
  )

  expect(screen.getByRole('heading', { level: 1, name: 'Applications' })).toHaveClass(
    'text-page-title',
  )
  expect(screen.getByRole('button', { name: 'Sync now' })).toBeInTheDocument()
})

test('renders without actions', () => {
  render(<PageTitle title="Applications" />)

  expect(screen.getByRole('heading', { level: 1 }).parentElement?.children).toHaveLength(1)
})
