/**
 * MSW Node server setup (SSR / tests).
 *
 * Reservado para Next.js server components o pruebas unitarias que necesiten
 * interceptar fetch en Node. El flujo actual del frontend hace fetch desde el
 * cliente, por lo que el bootstrap principal es `browser.ts`.
 */

import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
