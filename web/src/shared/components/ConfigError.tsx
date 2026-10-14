import type { EnvVar } from '@/config'

export function ConfigError({ missing }: { missing: EnvVar[] }) {
  return (
    <main role="alert" className="mx-auto max-w-xl p-8">
      <h1 className="text-xl font-semibold">Jats is missing its configuration</h1>
      <p className="mt-3 text-muted">
        Set {missing.length === 1 ? 'this environment variable' : 'these environment variables'} in{' '}
        <code className="font-mono">web/.env</code> and restart the dev server:
      </p>
      <ul className="mt-3 list-disc pl-6 font-mono">
        {missing.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
      <p className="mt-3 text-muted">
        <code className="font-mono">web/.env.example</code> lists every variable.
      </p>
    </main>
  )
}
