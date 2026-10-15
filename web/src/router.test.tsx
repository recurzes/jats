import { screen } from '@testing-library/react'
import { createFakeAuth } from '@/test/fakeAuth'
import { renderRoutes } from '@/test/renderRoutes'

test('/ shows the board inside the shell', async () => {
  renderRoutes('/')

  expect(await screen.findByRole('heading', { level: 1, name: 'Applications' })).toBeInTheDocument()
  expect(screen.getByRole('banner')).toBeInTheDocument()
})

test('/login shows the login form outside the shell', async () => {
  renderRoutes('/login', { auth: createFakeAuth().auth })

  expect(await screen.findByRole('heading', { name: 'Log in to Jats' })).toBeInTheDocument()
  expect(screen.queryByRole('banner')).not.toBeInTheDocument()
})
