import { readConfig } from '@/config'

const fullEnv = {
  VITE_API_URL: 'http://localhost:8000/',
  VITE_SUPABASE_URL: 'https://example.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'anon-key',
  VITE_USE_MOCKS: 'true',
}

test('reads every variable', () => {
  expect(readConfig(fullEnv)).toEqual({
    ok: true,
    config: {
      apiUrl: 'http://localhost:8000',
      supabaseUrl: 'https://example.supabase.co',
      supabaseAnonKey: 'anon-key',
      useMocks: true,
    },
  })
})

test('useMocks is false unless the value is "true"', () => {
  const result = readConfig({ ...fullEnv, VITE_USE_MOCKS: 'false' })

  expect(result.ok && result.config.useMocks).toBe(false)
})

test('names every missing or blank variable', () => {
  const result = readConfig({ ...fullEnv, VITE_API_URL: undefined, VITE_SUPABASE_ANON_KEY: ' ' })

  expect(result).toEqual({ ok: false, missing: ['VITE_API_URL', 'VITE_SUPABASE_ANON_KEY'] })
})
