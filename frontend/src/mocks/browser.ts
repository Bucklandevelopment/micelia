/**
 * MSW browser worker setup.
 *
 * Sólo se carga dinámicamente desde `MSWProvider` cuando
 * `NEXT_PUBLIC_USE_MOCK === 'true'`. El service worker se sirve desde
 * `/public/mockServiceWorker.js` (generado por `npm run msw:init`).
 */

import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

export const worker = setupWorker(...handlers)
