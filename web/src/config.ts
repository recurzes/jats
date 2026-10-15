export const ENV_VARS = ['VITE_API_URL', 'VITE_NEON_AUTH_URL', 'VITE_USE_MOCKS'] as const

export type EnvVar = (typeof ENV_VARS)[number]

export interface Config {
  apiUrl: string
  neonAuthUrl: string
  useMocks: boolean
}

export type ConfigResult = { ok: true; config: Config } | { ok: false; missing: EnvVar[] }

export function readConfig(env: Partial<Record<EnvVar, string | undefined>>): ConfigResult {
  const missing = ENV_VARS.filter((name) => !env[name]?.trim())
  if (missing.length > 0) return { ok: false, missing }

  return {
    ok: true,
    config: {
      apiUrl: env.VITE_API_URL!.replace(/\/+$/, ''),
      neonAuthUrl: env.VITE_NEON_AUTH_URL!,
      useMocks: env.VITE_USE_MOCKS === 'true',
    },
  }
}

export const configResult = readConfig(import.meta.env)

/**
 * Safe to use anywhere inside <App />: main.tsx renders the error screen instead of the app
 * when a variable is missing.
 */
export const config = (configResult.ok ? configResult.config : undefined) as Config
