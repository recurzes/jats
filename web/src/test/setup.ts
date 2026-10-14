import '@testing-library/jest-dom/vitest'
import { resetDb } from '@/mocks/db'
import { server } from '@/test/server'

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetDb()
})
afterAll(() => server.close())
