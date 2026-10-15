import { render, screen } from '@testing-library/react'
import type { ApplicationSummary } from '@/api/types'
import { ApplicationCard } from '@/features/board/ApplicationCard'
import { applications } from '@/mocks/fixtures'

function renderCard(changes: Partial<ApplicationSummary> = {}) {
  const application = { ...applications[0], ...changes }
  render(<ApplicationCard application={application} />)
  return screen.getByRole('article')
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
