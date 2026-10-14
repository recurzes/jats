import { act, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { apiRequest } from '@/api/client'
import { createFakeAuth } from '@/test/fakeAuth'
import { renderRoutes } from '@/test/renderRoutes'
import { server } from '@/test/server'

test('logged out: / redirects to /login', async () => {
  const { router } = renderRoutes('/', { auth: createFakeAuth().auth })

  expect(await screen.findByRole('heading', { name: 'Log in to Jats' })).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/login')
})

test('loading: shows a spinner and stays put', () => {
  const { mock, auth } = createFakeAuth()
  mock.getSession.mockReturnValueOnce(new Promise(() => {}))
  const { router } = renderRoutes('/', { auth })

  expect(screen.getByRole('status')).toHaveTextContent('Loading')
  expect(screen.queryByText('Board placeholder.')).not.toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/')
})

test('logged in: / shows the board', async () => {
  renderRoutes('/')

  expect(await screen.findByText('Board placeholder.')).toBeInTheDocument()
})

test('logged in: /login goes to /', async () => {
  const { router } = renderRoutes('/login')

  expect(await screen.findByText('Board placeholder.')).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/')
})

test('a 401 sends you to /login with "Session expired"', async () => {
  server.use(
    http.get('http://api.test/thing', () =>
      HttpResponse.json({ error: { code: 'AUTH_INVALID', message: 'Expired' } }, { status: 401 }),
    ),
  )
  const { router } = renderRoutes('/')
  await screen.findByText('Board placeholder.')

  await act(() => apiRequest('/thing').catch(() => undefined))

  expect(await screen.findByText('Session expired')).toHaveAttribute('role', 'status')
  expect(router.state.location.pathname).toBe('/login')
})
