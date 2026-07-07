'use client'

/**
 * MSWProvider — bootstrap del Mock Service Worker en el cliente.
 *
 * Se monta una sola vez en `app/providers.tsx`. Si `NEXT_PUBLIC_USE_MOCK`
 * no es `'true'`, el componente es un no-op y renderiza children directamente.
 *
 * Cuando el mock está activo:
 *   1. Importa dinámicamente `./browser` (evita incluir MSW en el bundle prod).
 *   2. Arranca el worker con `onUnhandledRequest: 'bypass'` para no romper
 *      Next.js HMR ni assets estáticos.
 *   3. Siembra tokens mock en localStorage + cookie para que el middleware
 *      no redirija a `/login` en cada navegación.
 *   4. Bloquea el render de children hasta que el worker está listo
 *      (evita una primera fetch que se escape sin interceptar).
 */

import { useEffect, useState } from 'react'

const MOCK_ACCESS_TOKEN = 'mock-access-token'
const MOCK_REFRESH_TOKEN = 'mock-refresh-token'

const MOCK_ENABLED =
  process.env.NEXT_PUBLIC_USE_MOCK === 'true' &&
  process.env.NODE_ENV !== 'production'

function seedAuthTokens(): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem('vital_access_token', MOCK_ACCESS_TOKEN)
    localStorage.setItem('vital_refresh_token', MOCK_REFRESH_TOKEN)
    document.cookie = `vital_auth=${MOCK_ACCESS_TOKEN}; path=/; max-age=${
      60 * 60 * 24
    }; SameSite=Lax`
  } catch {
    // localStorage might be unavailable (private mode); seguimos sin bloquear.
  }
}

export function MSWProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(!MOCK_ENABLED)

  useEffect(() => {
    if (!MOCK_ENABLED) return
    let cancelled = false

    void (async () => {
      const { worker } = await import('./browser')
      await worker.start({
        onUnhandledRequest: 'bypass',
        serviceWorker: { url: '/mockServiceWorker.js' },
      })
      seedAuthTokens()
      if (!cancelled) {
        // eslint-disable-next-line no-console
        console.info('[MSW] mock mode active — backend requests are intercepted')
        setReady(true)
      }
    })().catch((err) => {
      // eslint-disable-next-line no-console
      console.error('[MSW] failed to start worker', err)
      // Fallback: deja renderizar igualmente para no bloquear la UI.
      if (!cancelled) setReady(true)
    })

    return () => {
      cancelled = true
    }
  }, [])

  if (!ready) return null
  return <>{children}</>
}
