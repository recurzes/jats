import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { useSelectedApp } from '@/features/detail/useSelectedApp'

function Probe() {
  const { id, open, close } = useSelectedApp()
  return (
    <>
      <output>{id ?? 'none'}</output>
      <button onClick={() => open('abc')}>Open</button>
      <button onClick={close}>Close</button>
    </>
  )
}

function renderProbe(entry = '/') {
  const router = createMemoryRouter([{ path: '/', element: <Probe /> }], {
    initialEntries: [entry],
  })
  render(<RouterProvider router={router} />)
  return router
}

const selected = () => screen.getByRole('status').textContent

test('reads the id from ?app=', () => {
  renderProbe('/?app=xyz')

  expect(selected()).toBe('xyz')
})

test('no ?app= means nothing is open', () => {
  renderProbe('/')

  expect(selected()).toBe('none')
})

test('open pushes a history entry, so Back closes the panel', async () => {
  const router = renderProbe('/')

  await userEvent.click(screen.getByRole('button', { name: 'Open' }))
  expect(router.state.location.search).toBe('?app=abc')
  expect(selected()).toBe('abc')

  await act(() => router.navigate(-1))
  expect(router.state.location.search).toBe('')
  expect(selected()).toBe('none')
})

test('open and close keep other parameters', async () => {
  const router = renderProbe('/?gmail=connected')

  await userEvent.click(screen.getByRole('button', { name: 'Open' }))
  expect(new URLSearchParams(router.state.location.search).get('gmail')).toBe('connected')

  await userEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(router.state.location.search).toBe('?gmail=connected')
  expect(selected()).toBe('none')
})

test('close after open steps back instead of adding an entry', async () => {
  const router = renderProbe('/')

  await userEvent.click(screen.getByRole('button', { name: 'Open' }))
  await userEvent.click(screen.getByRole('button', { name: 'Close' }))

  expect(router.state.historyAction).toBe('POP')
  expect(router.state.location.search).toBe('')
})

test('close on a page loaded with ?app= removes it in place', async () => {
  const router = renderProbe('/?app=xyz&gmail=connected')

  await userEvent.click(screen.getByRole('button', { name: 'Close' }))

  expect(router.state.historyAction).toBe('REPLACE')
  expect(router.state.location.search).toBe('?gmail=connected')
  expect(selected()).toBe('none')
})
