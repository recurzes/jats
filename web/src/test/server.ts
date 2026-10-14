import { setupServer } from 'msw/node'
import { handlers } from '@/mocks/handlers'

/** The mock API in Node. Override a route for one test with `server.use(...)`. */
export const server = setupServer(...handlers)
