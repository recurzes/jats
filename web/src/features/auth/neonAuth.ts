import { createAuthClient, type VanillaBetterAuthClient } from '@neondatabase/neon-js/auth'
import { BetterAuthVanillaAdapter } from '@neondatabase/neon-js/auth/vanilla/adapters'
import { config } from '@/config'

/** The signed-in user. The access token is read separately, at request time. */
export interface Session {
  user: { id: string; email: string }
}

/** The auth calls the app makes. Tests pass a fake. */
export interface AuthClient {
  getSession(): Promise<Session | null>
  /** Resolves to false when the server refuses the login; may throw when it cannot be reached. */
  signIn(email: string, password: string): Promise<boolean>
  signOut(): Promise<void>
  /** The Neon Auth JWT the API checks, or null when signed out. */
  getToken(): Promise<string | null>
}

/**
 * Neon Auth is used only for login: all data goes through the API. Created on first use,
 * because this module loads even when the config is missing.
 */
let client: AuthClient | undefined

export function getAuthClient() {
  client ??= adapt(createAuthClient(config.neonAuthUrl, { adapter: BetterAuthVanillaAdapter() }))
  return client
}

// Fetch a new token this long before the cached one expires, so it never expires in flight.
const REFRESH_MARGIN_MS = 60_000

/** When a JWT expires, in ms since the epoch, or 0 when it cannot be read. */
function expiresAt(jwt: string) {
  try {
    const payload = jwt.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const exp = (JSON.parse(atob(payload)) as { exp?: unknown }).exp
    return typeof exp === 'number' ? exp * 1000 : 0
  } catch {
    return 0
  }
}

export function adapt(auth: VanillaBetterAuthClient): AuthClient {
  // The API needs the signed JWT from `token()`. `session.token` is the opaque session id.
  let cached: { token: string; expiresAt: number } | null = null

  async function readSession() {
    const { data } = await auth.getSession()
    // Signed out, or only an anonymous session.
    return data && 'user' in data ? data : null
  }

  return {
    async getSession() {
      const user = (await readSession())?.user
      return user ? { user: { id: user.id, email: user.email } } : null
    },
    async signIn(email, password) {
      const { error } = await auth.signIn.email({ email, password })
      return !error
    },
    async signOut() {
      cached = null
      await auth.signOut()
    },
    async getToken() {
      if (cached && Date.now() < cached.expiresAt - REFRESH_MARGIN_MS) return cached.token
      cached = null
      try {
        const token = (await auth.token()).data?.token
        if (!token) return null
        cached = { token, expiresAt: expiresAt(token) }
        return token
      } catch {
        return null
      }
    },
  }
}
