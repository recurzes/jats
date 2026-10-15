import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createFakeAuth, PASSWORD } from '@/test/fakeAuth'
import { renderRoutes } from '@/test/renderRoutes'

async function logIn(password: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Email'), 'me@example.com')
  await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Log in' }))
}

test('labelled fields that password managers can fill', async () => {
  renderRoutes('/login', { auth: createFakeAuth().auth })

  expect(await screen.findByLabelText('Email')).toHaveAttribute('autocomplete', 'email')
  expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password')
  expect(screen.queryByText(/sign up/i)).not.toBeInTheDocument()
})

test('a wrong password shows one inline error', async () => {
  const { mock, auth } = createFakeAuth()
  renderRoutes('/login', { auth })

  await logIn('wrong')

  expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password')
  expect(screen.getByRole('button', { name: 'Log in' })).toBeEnabled()
  expect(mock.signIn).toHaveBeenCalledWith('me@example.com', 'wrong')
})

test('a network failure shows the same error', async () => {
  const { mock, auth } = createFakeAuth()
  mock.signIn.mockRejectedValueOnce(new TypeError('Failed to fetch'))
  renderRoutes('/login', { auth })

  await logIn(PASSWORD)

  expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password')
})

test('the button is disabled while waiting', async () => {
  const { mock, auth } = createFakeAuth()
  mock.signIn.mockReturnValueOnce(new Promise(() => {}))
  renderRoutes('/login', { auth })

  await logIn(PASSWORD)

  expect(screen.getByRole('button', { name: 'Logging in…' })).toBeDisabled()
})

test('success goes to the board', async () => {
  const { router } = renderRoutes('/login', { auth: createFakeAuth().auth })

  await logIn(PASSWORD)

  expect(await screen.findByText('Board placeholder.')).toBeInTheDocument()
  expect(router.state.location.pathname).toBe('/')
})

test('shows the notice passed in router state', async () => {
  renderRoutes(
    { pathname: '/login', state: { notice: 'Session expired' } },
    { auth: createFakeAuth().auth },
  )

  expect(await screen.findByText('Session expired')).toHaveAttribute('role', 'status')
})
