import { render, screen, within } from '@testing-library/react'
import type { StatusEvent } from '@/api/types'
import { StatusHistory } from '@/features/detail/StatusHistory'
import { applicationDetail } from '@/mocks/fixtures'

const manualEvent: StatusEvent = {
  id: 'manual-1',
  from_status: 'replied',
  to_status: 'rejected',
  source: 'manual',
  email_id: null,
  created_at: '2026-10-14T09:00:00Z',
}

test('an ordered list, newest first, as the API sends it', () => {
  render(<StatusHistory events={applicationDetail.status_events} />)

  const items = within(screen.getByRole('list')).getAllByRole('listitem')
  expect(screen.getByRole('list').tagName).toBe('OL')
  expect(items.map((item) => item.querySelector('p')?.textContent)).toEqual([
    'Acknowledged to Replied',
    'Started as Acknowledged',
  ])
})

test('the first event says "Started as", never "null"', () => {
  const { container } = render(<StatusHistory events={applicationDetail.status_events} />)

  expect(screen.getByText('Started as Acknowledged')).toBeInTheDocument()
  expect(container).not.toHaveTextContent('null')
})

test('date and time in mono, and the source', () => {
  render(<StatusHistory events={[manualEvent, ...applicationDetail.status_events]} />)

  const [manual, fromEmail] = screen.getAllByRole('listitem')
  const time = manual.querySelector('time')
  expect(time).toHaveAttribute('dateTime', manualEvent.created_at)
  expect(time).toHaveClass('font-mono')
  expect(time?.textContent).toMatch(/^Oct 1[45], \d{2}:\d{2}$/)
  expect(manual).toHaveTextContent('Replied to Rejected')
  expect(manual).toHaveTextContent('manual')
  expect(fromEmail).toHaveTextContent('from email')
})

test('a dot per event in its new status colour', () => {
  render(<StatusHistory events={applicationDetail.status_events} />)

  const dots = screen.getAllByRole('listitem').map((item) => item.querySelector('[data-status]'))
  expect(dots.map((dot) => dot?.getAttribute('data-status'))).toEqual(['replied', 'acknowledged'])
})
