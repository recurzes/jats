import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderRoutes } from '@/test/renderRoutes'

test('Sign out returns to /login with an empty cache', async () => {
  const { router, queryClient } = renderRoutes('/')
  queryClient.setQueryData(['applications'], [])

  await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))

  expect(await screen.findByRole('heading', { name: 'Log in to Jats' })).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/login')
  expect(queryClient.getQueryData(['applications'])).toBeUndefined()
  // A plain sign-out carries no notice.
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
