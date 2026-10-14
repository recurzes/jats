import { config } from '@/config'
import type { ApiErrorBody } from '@/api/types'

/** Every failed request. `status` is 0 when the request never got a response. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

type TokenGetter = () => string | null | Promise<string | null>

let getToken: TokenGetter = () => null

/** Supplies the bearer token sent with every request. `AuthProvider` wires it to the session. */
export function setTokenGetter(getter: TokenGetter) {
  getToken = getter
}

type AuthFailureHandler = (error: ApiError) => void

let onAuthFailure: AuthFailureHandler = () => {}

/** Called before throwing a 401, or a 403 `NOT_OWNER`, so the session can end. */
export function setAuthFailureHandler(handler: AuthFailureHandler) {
  onAuthFailure = handler
}

function isAuthFailure(error: ApiError) {
  return error.status === 401 || error.code === 'NOT_OWNER'
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | undefined>
}

function buildUrl(path: string, query: RequestOptions['query']) {
  const url = new URL(`${config.apiUrl}${path}`)
  for (const [name, value] of Object.entries(query ?? {})) {
    if (value !== undefined) url.searchParams.set(name, String(value))
  }
  return url
}

function isErrorBody(body: unknown): body is ApiErrorBody {
  const error = (body as ApiErrorBody | null)?.error
  return typeof error?.code === 'string' && typeof error.message === 'string'
}

async function readJson(response: Response): Promise<unknown> {
  // 202 and 204 responses may have nothing to parse.
  const text = await response.text()
  if (!text) return undefined
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}

/** The only place that calls `fetch`. Resolves with the parsed JSON body. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = await getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError('NETWORK', 'Could not reach the server', 0)
  }

  const data = await readJson(response)
  if (!response.ok) {
    const error = isErrorBody(data)
      ? new ApiError(data.error.code, data.error.message, response.status)
      : new ApiError(
          `HTTP_${response.status}`,
          response.statusText || `Request failed with status ${response.status}`,
          response.status,
        )
    if (isAuthFailure(error)) onAuthFailure(error)
    throw error
  }
  return data as T
}
