import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import type { ApplicationSummary } from '@/api/types'
import { ApplicationCard } from '@/features/board/ApplicationCard'
import { applications } from '@/mocks/fixtures'

// The card reads and writes ?app=, so it needs a router.
function renderCardWithRouter(changes: Partial<ApplicationSummary> = {}) {
  const application = { ...applications[0], ...changes }
  const router = createMemoryRouter([
    { path: '/', element: <ApplicationCard application={application} /> },
  ])
  render(<RouterProvider router={router} />)
  return { card: screen.getByRole('article'), router }
}

function renderCard(changes: Partial<ApplicationSummary> = {}) {
  return renderCardWithRouter(changes).card
}

test('renders company, role, last email subject and date from a fixture', () => {
  const card = renderCard()

  expect(screen.getByRole('heading', { name: 'Northwind Labs' })).toHaveClass('text-card-title')
  expect(screen.getByText('Frontend Engineer')).toHaveClass('text-muted')
  expect(screen.getByText('Next steps: technical interview')).toHaveAttribute(
    'title',
    'Next steps: technical interview',
  )
  const date = card.querySelector('time')
  expect(date).toHaveAttribute('dateTime', '2026-10-13T15:40:00Z')
  expect(date).toHaveClass('font-mono')
  expect(date?.textContent).toMatch(/^Oct 1[34]$/)
})

test('hides the role line when there is no role', () => {
  const card = renderCard({ role: null })

  expect(card).not.toHaveTextContent('null')
  expect(card.querySelectorAll('p')).toHaveLength(1)
})

test('hides the divider and email lines when no email has arrived', () => {
  const card = renderCard({ last_email_subject: null, last_email_at: null })

  expect(card.querySelector('time')).toBeNull()
  expect(card.querySelector('.border-t')).toBeNull()
  expect(card).not.toHaveTextContent('null')
})

describe('Needs review badge', () => {
  test('shows when flagged', () => {
    renderCard({ needs_review: true })

    expect(screen.getByText('Needs review')).toHaveAttribute('data-variant', 'review')
  })

  test('hidden otherwise', () => {
    renderCard({ needs_review: false })

    expect(screen.queryByText('Needs review')).not.toBeInTheDocument()
  })
})

describe('opening the panel', () => {
  test('the company is a button that sets ?app= on click', async () => {
    const { router } = renderCardWithRouter()

    await userEvent.click(screen.getByRole('button', { name: 'Northwind Labs' }))

    expect(router.state.location.search).toBe(`?app=${applications[0].id}`)
  })

  test('Tab then Enter opens it too', async () => {
    const { router } = renderCardWithRouter()

    await userEvent.tab()
    expect(screen.getByRole('button', { name: 'Northwind Labs' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')

    expect(router.state.location.search).toBe(`?app=${applications[0].id}`)
  })

  test('the button stretches over the whole card', () => {
    const card = renderCard()

    expect(card).toHaveClass('relative')
    expect(screen.getByRole('button')).toHaveClass('after:absolute', 'after:inset-0')
  })
})
