import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import type { RuntimeConfig } from './App.tsx'
import { publicAnalyticsHeaders } from './lib/publicAnalytics.ts'
import { ErrorBoundary } from './ui/ErrorBoundary'

async function start() {
  const response = await fetch('/api/session', { credentials: 'same-origin' })
  if (!response.ok) throw new Error('Unable to establish API session')
  const runtimeResponse = await fetch('/api/runtime', {
    credentials: 'same-origin',
    headers: publicAnalyticsHeaders(
      window.location.search,
      document.referrer,
      window.location.hostname,
    ),
  })
  if (!runtimeResponse.ok) throw new Error('Unable to load runtime configuration')
  const runtime = await runtimeResponse.json() as RuntimeConfig

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ErrorBoundary>
        <App runtime={runtime} />
      </ErrorBoundary>
    </StrictMode>,
  )
}

void start()
