import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/600.css'
import '@/styles/index.css'
import App from '@/App'
import { configResult } from '@/config'
import { ConfigError } from '@/shared/components/ConfigError'

// Before the first render, or the first requests race past the worker.
// Imported only here: the handlers read the config, which may be missing.
if (configResult.ok && configResult.config.useMocks) {
  const { worker } = await import('@/mocks/browser')
  await worker.start({ onUnhandledFrame: 'bypass' })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {configResult.ok ? <App /> : <ConfigError missing={configResult.missing} />}
  </StrictMode>,
)
