import { createClient, type SupabaseClient } from '@supabase/supabase-js'
import { config } from '@/config'

/**
 * Supabase is used only for login. Never call `supabase.from(...)`: all data goes through the
 * API. Created on first use, because this module loads even when the config is missing.
 */
let client: SupabaseClient | undefined

export function getSupabase() {
  client ??= createClient(config.supabaseUrl, config.supabaseAnonKey)
  return client
}

/** The part of the Supabase auth API the app uses. Tests pass a fake. */
export type AuthClient = Pick<
  SupabaseClient['auth'],
  'getSession' | 'onAuthStateChange' | 'signInWithPassword' | 'signOut'
>
