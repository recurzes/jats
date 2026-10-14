import { getSupabase } from '@/features/auth/supabase'

test('creates one Supabase client from the config', () => {
  const client = getSupabase()

  expect(client.auth).toBeDefined()
  expect(getSupabase()).toBe(client)
})
