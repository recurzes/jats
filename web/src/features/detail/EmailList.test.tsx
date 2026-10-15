import { render, screen } from '@testing-library/react'
import { EmailList } from '@/features/detail/EmailList'
import { applicationDetail } from '@/mocks/fixtures'

test('shows the three mock emails with subject, sender, date and snippet', () => {
  render(<EmailList emails={applicationDetail.emails} />)

  const items = screen.getAllByRole('listitem')
  expect(items).toHaveLength(3)

  const [first] = applicationDetail.emails
  expect(screen.getByRole('heading', { name: first.subject })).toBeInTheDocument()
  expect(screen.getByText(first.from_address)).toHaveClass('font-mono')
  expect(screen.getByText(first.snippet)).toBeInTheDocument()
  const time = items[0].querySelector('time')
  expect(time).toHaveAttribute('dateTime', first.received_at)
  expect(time?.textContent).toMatch(/^Oct 1[34]$/)
})

test('says "No emails" when there are none', () => {
  render(<EmailList emails={[]} />)

  expect(screen.getByText('No emails')).toBeInTheDocument()
  expect(screen.queryByRole('list')).not.toBeInTheDocument()
})

test('renders the snippet as text, never as HTML', () => {
  const snippet = '<img src=x onerror="alert(1)"><b>bold</b>'
  const { container } = render(<EmailList emails={[{ ...applicationDetail.emails[0], snippet }]} />)

  expect(screen.getByText(snippet)).toBeInTheDocument()
  expect(container.querySelector('img')).toBeNull()
  expect(container.querySelector('b')).toBeNull()
})
