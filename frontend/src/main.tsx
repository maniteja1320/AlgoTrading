import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import App from './App'
import { ErrorBoundary } from './ErrorBoundary'
import './index.css'

if ('serviceWorker' in navigator) {
  registerSW({ immediate: true })
}
function showBootstrapError(message: string) {
  const root = document.getElementById('root')
  if (!root || root.childElementCount > 0) return
  root.innerHTML = `
    <div style="padding:24px;font-family:system-ui,sans-serif;color:#e8edf5;background:#0a0e17;min-height:100vh">
      <h1 style="font-size:1.25rem;margin-bottom:12px">Failed to load app</h1>
      <p style="color:#8b9cb8;margin-bottom:16px">Try Ctrl+Shift+R (hard refresh) or clear site data for localhost.</p>
      <pre style="background:#111827;padding:16px;border-radius:8px;overflow:auto;font-size:0.85rem">${message}</pre>
    </div>`
}

window.addEventListener('error', (event) => {
  showBootstrapError(event.message || 'Unknown script error')
})

window.addEventListener('unhandledrejection', (event) => {
  const msg = event.reason instanceof Error ? event.reason.message : String(event.reason)
  showBootstrapError(msg)
})

try {
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </StrictMode>,
  )
} catch (e) {
  showBootstrapError(e instanceof Error ? e.message : 'Mount failed')
}