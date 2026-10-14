import { render, screen } from '@testing-library/react'
import App from '@/App'
import { createQueryClient } from '@/queryClient'
import { createFakeAuth, fakeSession } from '@/test/fakeAuth'

test('renders the app', async () => {
  render(<App queryClient={createQueryClient()} auth={createFakeAuth(fakeSession()).auth} />)

  expect(await screen.findByRole('heading', { name: 'Jats' })).toBeInTheDocument()
})
