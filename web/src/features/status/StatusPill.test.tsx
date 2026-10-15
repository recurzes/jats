import { render, screen } from '@testing-library/react'
import { StatusPill, type StatusTone } from '@/features/status/StatusPill'

const tones: StatusTone[] = ['good', 'warning', 'error']

// Story-style: every tone side by side, the way the strip shows them.
function AllTones() {
  return (
    <div className="flex gap-2">
      {tones.map((tone) => (
        <StatusPill key={tone} tone={tone}>
          Tone {tone}
        </StatusPill>
      ))}
    </div>
  )
}

test('renders every tone with its dot colour', () => {
  render(<AllTones />)

  for (const tone of tones) {
    const pill = screen.getByText(`Tone ${tone}`)
    expect(pill).toHaveAttribute('data-tone', tone)
    expect(pill.querySelector('[aria-hidden]')).toHaveClass(`bg-${tone}`)
  }
})

test('the dot is hidden, so the text alone is announced', () => {
  render(<StatusPill tone="error">Printer offline</StatusPill>)

  expect(screen.getByText('Printer offline')).toHaveTextContent(/^Printer offline$/)
  expect(screen.getByText('Printer offline').querySelector('[aria-hidden]')).toBeEmptyDOMElement()
})

test('passes extra props to the pill', () => {
  render(
    <StatusPill tone="good" tabIndex={0} className="extra">
      Printer online
    </StatusPill>,
  )

  expect(screen.getByText('Printer online')).toHaveAttribute('tabindex', '0')
  expect(screen.getByText('Printer online')).toHaveClass('extra')
})
