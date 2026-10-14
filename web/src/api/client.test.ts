import { http, HttpResponse } from 'msw'
import { ApiError, apiRequest, setTokenGetter } from '@/api/client'
import { server } from '@/test/server'

const url = 'http://api.test/thing'

async function failure(promise: Promise<unknown>) {
  const error = await promise.then(
    () => undefined,
    (reason: unknown) => reason,
  )
  expect(error).toBeInstanceOf(ApiError)
  return error as ApiError
}

afterEach(() => setTokenGetter(() => null))

test('200 resolves with the JSON body', async () => {
  server.use(http.get(url, () => HttpResponse.json({ ok: true })))

  await expect(apiRequest('/thing')).resolves.toEqual({ ok: true })
})

test('an empty 2xx body resolves with undefined', async () => {
  server.use(http.post(url, () => new HttpResponse(null, { status: 204 })))

  await expect(apiRequest('/thing', { method: 'POST' })).resolves.toBeUndefined()
})

test('sends the body as JSON and skips undefined query values', async () => {
  let seen: { url: string; contentType: string | null; body: unknown } | undefined
  server.use(
    http.patch(url, async ({ request }) => {
      seen = {
        url: request.url,
        contentType: request.headers.get('Content-Type'),
        body: await request.json(),
      }
      return HttpResponse.json({})
    }),
  )

  await apiRequest('/thing', {
    method: 'PATCH',
    body: { a: 1 },
    query: { status: 'replied', needs_review: false, other: undefined },
  })

  expect(seen).toEqual({
    url: `${url}?status=replied&needs_review=false`,
    contentType: 'application/json',
    body: { a: 1 },
  })
})

test('sends the token from the getter as a bearer header', async () => {
  let authorization: string | null = null
  server.use(
    http.get(url, ({ request }) => {
      authorization = request.headers.get('Authorization')
      return HttpResponse.json({})
    }),
  )
  setTokenGetter(async () => 'secret-token')

  await apiRequest('/thing')

  expect(authorization).toBe('Bearer secret-token')
})

test('sends no auth header without a token', async () => {
  let authorization: string | null = 'unset'
  server.use(
    http.get(url, ({ request }) => {
      authorization = request.headers.get('Authorization')
      return HttpResponse.json({})
    }),
  )

  await apiRequest('/thing')

  expect(authorization).toBeNull()
})

test('401 becomes an ApiError with the code from the body', async () => {
  server.use(
    http.get(url, () =>
      HttpResponse.json(
        { error: { code: 'AUTH_INVALID', message: 'Token expired' } },
        { status: 401 },
      ),
    ),
  )

  const error = await failure(apiRequest('/thing'))

  expect(error).toMatchObject({ code: 'AUTH_INVALID', message: 'Token expired', status: 401 })
})

test('404 from the mock API is NOT_FOUND', async () => {
  const error = await failure(apiRequest('/applications/missing'))

  expect(error).toMatchObject({
    code: 'NOT_FOUND',
    message: 'Application not found',
    status: 404,
  })
})

test('500 without a JSON body falls back to HTTP_500', async () => {
  server.use(http.get(url, () => new HttpResponse('Bad gateway', { status: 500 })))

  const error = await failure(apiRequest('/thing'))

  expect(error).toMatchObject({ code: 'HTTP_500', status: 500 })
})

test('500 with the error body keeps its code', async () => {
  server.use(
    http.get(url, () =>
      HttpResponse.json(
        { error: { code: 'INTERNAL', message: 'Internal server error' } },
        { status: 500 },
      ),
    ),
  )

  const error = await failure(apiRequest('/thing'))

  expect(error).toMatchObject({ code: 'INTERNAL', status: 500 })
})

test('a network failure is NETWORK with status 0', async () => {
  server.use(http.get(url, () => HttpResponse.error()))

  const error = await failure(apiRequest('/thing'))

  expect(error).toMatchObject({ code: 'NETWORK', status: 0 })
  expect(error).toBeInstanceOf(Error)
})
