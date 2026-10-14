import { render, screen } from '@testing-library/react'
import { ConfigError } from '@/shared/components/ConfigError'

test('names the missing variables', () => {
  render(<ConfigError missing={['VITE_API_URL', 'VITE_USE_MOCKS']} />)

  expect(screen.getByRole('alert')).toBeInTheDocument()
  expect(screen.getByText('VITE_API_URL')).toBeInTheDocument()
  expect(screen.getByText('VITE_USE_MOCKS')).toBeInTheDocument()
})
