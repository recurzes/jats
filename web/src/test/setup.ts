import '@testing-library/jest-dom/vitest'
import { resetDb } from '@/mocks/db'
import { server } from '@/test/server'

// jsdom has no ResizeObserver; Radix popovers and tooltips measure with it.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => server.listen({ onUnhandledFrame: 'error' }))
afterEach(() => {
  server.resetHandlers()
  resetDb()
})
afterAll(() => server.close())
