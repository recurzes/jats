import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { routes } from '@/router'

function renderAt(path: string) {
  render(<RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />)
}

test('/ shows the board inside the shell', async () => {
  renderAt('/')

  expect(await screen.findByText('Board placeholder.')).toBeInTheDocument()
  expect(screen.getByRole('banner')).toBeInTheDocument()
})

test('/login shows the login placeholder outside the shell', async () => {
  renderAt('/login')

  expect(await screen.findByText('Login form placeholder.')).toBeInTheDocument()
  expect(screen.queryByRole('banner')).not.toBeInTheDocument()
})
