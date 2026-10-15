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

test('renders without actions or meta', () => {
  const { container } = render(<PageTitle title="Applications" />)

  expect(container.firstElementChild?.children).toHaveLength(1)
  expect(screen.getByRole('heading', { level: 1 }).parentElement?.children).toHaveLength(1)
})

test('renders the meta in mono next to the title', () => {
  render(<PageTitle title="Applications" meta="9 tracked" />)

  expect(screen.getByText('9 tracked')).toHaveClass('font-mono')
})
