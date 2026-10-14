import { render, screen } from '@testing-library/react'
import App from '@/App'
import { createQueryClient } from '@/queryClient'

test('renders the app', async () => {
  render(<App queryClient={createQueryClient()} />)

  expect(await screen.findByRole('heading', { name: 'Jats' })).toBeInTheDocument()
})
