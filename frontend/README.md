# Micelia — Frontend (Next.js 14)

Dashboard del orquestador Micelia. App Router, TypeScript estricto,
TanStack Query, Tailwind. Escucha en `http://localhost:3001` y consume
el backend FastAPI en `http://localhost:8888` por defecto.

---

## Arranque rápido

```bash
# Desde la raíz del repo
make frontend-install      # npm install
make frontend-dev          # backend real (necesita Micelia en :8888)
make frontend-dev-mock     # backend mockeado vía MSW (no necesita backend)
```

Lint y type-check:

```bash
make frontend-lint
```

---

## Modo mock (MSW) — T4.1

Sirve el dashboard contra un backend simulado en el browser. Útil para:

- Iteración de UI sin levantar FastAPI + Postgres + Redis + Ollama.
- QA manual (T4.2) sin depender del orquestador real.
- Demos y screenshots reproducibles.

### Primer arranque

```bash
cd frontend
npm install                # instala MSW como dev dep
npm run msw:init           # genera public/mockServiceWorker.js (una sola vez)
cp .env.local.example .env.local
# edita .env.local y pon NEXT_PUBLIC_USE_MOCK=true
npm run dev:mock           # o, desde la raíz: make frontend-dev-mock
```

El comando `make frontend-dev-mock` ejecuta `msw init` automáticamente
si `public/mockServiceWorker.js` no existe, así que basta con un único
`make frontend-dev-mock` tras `make frontend-install`.

### Cómo funciona

1. `src/mocks/MSWProvider.tsx` se monta en `app/providers.tsx`.
2. Si `NEXT_PUBLIC_USE_MOCK=true` y `NODE_ENV !== production`, importa
   dinámicamente `src/mocks/browser.ts` y arranca el service worker.
3. El worker intercepta todas las peticiones a `/api/v1/*` y responde
   con los handlers de `src/mocks/handlers.ts`.
4. Para evitar redirecciones a `/login`, el provider siembra tokens
   mock (`mock-access-token`) en `localStorage` y en la cookie
   `vital_auth` que lee el middleware.

### Endpoints mockeados

| Dominio    | Endpoints                                                            |
|------------|----------------------------------------------------------------------|
| Auth       | `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`             |
| Health     | `GET /health`, `/health/live`, `/health/ready`, `/health/detailed`, `/health/services` |
| System     | `GET /system/info`, `/system/apps`, `/system/volume`, `/system/dark-mode`, `/system/clipboard`, `POST /system/notify` |
| AI         | `GET /ai/status`, `/ai/models`                                       |
| Energy     | `GET /energy/status`, `/energy/history`, `/energy/compute-recommendation` |
| Events     | `GET /events`, `POST /events`, `GET /events/categories`, `/events/stats` |
| Prompts    | `GET /prompts`, `/prompts/stats`, `/prompts/inbox`, `/prompts/staging`, `/prompts/archive`, `/prompts/pipeline/status`, `/prompts/lists`, `GET /prompts/:id`, `POST /prompts`, `POST /prompts/notes` |
| Dashboard  | `GET /dashboard/summary`                                             |
| Calendar   | `GET /calendar/status`, `/calendar/events`, `/calendar/calendars`    |
| Skills     | `GET /skills`                                                        |
| MCP        | `GET /mcp/servers`, `/mcp/templates`                                 |
| Agents     | `GET /agents/crews`, `/agents/workflows`, `/agents/runs`             |
| Tunnel     | `GET /tunnel/status`                                                 |

Las shapes siguen `src/types/api.ts` y los contratos canónicos en
`tests/e2e/mocks/contracts.py`.

### Añadir un handler nuevo

1. Abre `src/mocks/handlers.ts`.
2. Localiza el bloque del dominio correspondiente (o crea uno nuevo).
3. Añade un `http.METHOD('/api/v1/...', () => HttpResponse.json({...}))`.
4. Inclúyelo en el array exportado `handlers`.
5. Si el endpoint tiene un tipo en `src/types/api.ts`, respeta la shape.
6. Recarga el navegador — MSW no necesita rebuild.

### Páginas que funcionan en modo mock

- `/login` → introduce cualquier usuario/contraseña; redirige a `/`.
- `/` (Mission Control) → KPIs, queue preview, recent results, agents,
  calendar upcoming, energy y system status con datos sintéticos.
- `/monitor` → métricas de health y resources.
- `/prompts` → inbox, staging, archive y pipeline status.
- `/prompts/lists` → una lista de ejemplo.
- `/audit` → eventos sintéticos.
- `/agents` → workflows disponibles (sin runs).
- `/settings` → estado de servicios.

### Páginas con cobertura parcial

- `/calendar` → el mock devuelve `connected: false`, así que sólo se ve
  el estado vacío. Conectar Google Calendar requiere OAuth real.
- `/skills` y MCP servers → listados vacíos por defecto (suficiente
  para validar layouts; añade handlers si necesitas datos).

### Limitaciones conocidas

- **OAuth real** (Google Calendar) no se puede simular sin proxy server.
- **Streaming** (SSE, WebSocket) no está mockeado; los componentes que
  dependan de stream verán estado vacío.
- **Llamadas server-side** (Server Components, Route Handlers): MSW
  browser worker no las intercepta. Hoy todas las llamadas API son
  client-side (`'use client'` + react-query), así que no es un problema
  en la práctica.

---

## Variables de entorno

Ver `.env.local.example`. Las dos relevantes:

| Variable                | Default                  | Descripción                                 |
|-------------------------|--------------------------|---------------------------------------------|
| `IDM_CORE_API_URL`      | `http://localhost:8888`  | Backend FastAPI para las rewrites           |
| `NEXT_PUBLIC_USE_MOCK`  | `false`                  | Activa MSW en el cliente (sólo en dev)      |

---

## Scripts npm

| Script             | Acción                                                |
|--------------------|-------------------------------------------------------|
| `npm run dev`      | Next.js dev en :3001 contra backend real              |
| `npm run dev:mock` | Next.js dev con `NEXT_PUBLIC_USE_MOCK=true`           |
| `npm run build`    | Build de producción                                   |
| `npm run start`    | Sirve el build en :3001                               |
| `npm run lint`     | ESLint (config `next/core-web-vitals`)                |
| `npm run type-check` | `tsc --noEmit`                                      |
| `npm run msw:init` | Regenera `public/mockServiceWorker.js`                |
