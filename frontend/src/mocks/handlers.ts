/**
 * MSW request handlers para el modo mock del frontend Micelia.
 *
 * Se activan cuando `NEXT_PUBLIC_USE_MOCK=true`. Cubren los endpoints
 * mínimos para que el dashboard, login, monitor, prompts, agents,
 * calendar y settings sean navegables sin un backend FastAPI real.
 *
 * Convenciones:
 * - Las shapes siguen `tests/e2e/mocks/contracts.py` y `src/types/api.ts`.
 * - Las respuestas son deterministas: misma URL = misma payload.
 * - Los timestamps se generan en runtime para que el UI muestre datos
 *   recientes en cada arranque.
 *
 * Para añadir un endpoint:
 * 1. Crea un handler `http.METHOD('/api/v1/...', () => HttpResponse.json({...}))`
 * 2. Añádelo al array exportado `handlers`.
 * 3. Verifica que la shape coincide con `src/types/api.ts` (o añade el tipo).
 */

import { http, HttpResponse } from 'msw'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const now = () => new Date().toISOString()
const minutesAgo = (m: number) =>
  new Date(Date.now() - m * 60_000).toISOString()
const minutesAhead = (m: number) =>
  new Date(Date.now() + m * 60_000).toISOString()

const MOCK_ACCESS_TOKEN = 'mock-access-token'
const MOCK_REFRESH_TOKEN = 'mock-refresh-token'

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

const authHandlers = [
  http.post('/api/v1/auth/register', async () => {
    // El backend real (POST /api/v1/auth/register) hace auto-login y devuelve
    // 201 con el par de tokens. Reproducimos esa shape para que
    // `authApi.register` → `setStoredTokens` → redirect a `/` funcione en modo
    // mock, igual que el flujo real register → login → dashboard.
    return HttpResponse.json(
      {
        access_token: MOCK_ACCESS_TOKEN,
        refresh_token: MOCK_REFRESH_TOKEN,
        token_type: 'bearer',
        expires_in: 86400,
      },
      { status: 201 }
    )
  }),

  http.post('/api/v1/auth/login', async () => {
    return HttpResponse.json({
      access_token: MOCK_ACCESS_TOKEN,
      refresh_token: MOCK_REFRESH_TOKEN,
      token_type: 'bearer',
      expires_in: 86400,
    })
  }),

  http.post('/api/v1/auth/refresh', async () => {
    return HttpResponse.json({
      access_token: MOCK_ACCESS_TOKEN,
      refresh_token: MOCK_REFRESH_TOKEN,
      token_type: 'bearer',
      expires_in: 86400,
    })
  }),

  http.get('/api/v1/auth/me', () =>
    HttpResponse.json({
      username: 'mock-user',
      auth_method: 'jwt',
      auth_identity: 'mock-user@micelia.local',
    })
  ),
]

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

const healthHandlers = [
  http.get('/api/v1/health', () =>
    HttpResponse.json({ status: 'healthy', timestamp: now() })
  ),

  http.get('/api/v1/health/live', () =>
    HttpResponse.json({ status: 'alive', timestamp: now() })
  ),

  http.get('/api/v1/health/ready', () =>
    HttpResponse.json({ status: 'ready', timestamp: now() })
  ),

  http.get('/api/v1/health/detailed', () =>
    HttpResponse.json({
      status: 'healthy',
      timestamp: now(),
      uptime_seconds: 3_600,
      services: {
        postgres: {
          name: 'postgres',
          url: 'postgresql://localhost:5432',
          enabled: true,
          healthy: true,
          latency_ms: 4.2,
        },
        redis: {
          name: 'redis',
          url: 'redis://localhost:6379',
          enabled: true,
          healthy: true,
          latency_ms: 1.1,
        },
        ollama: {
          name: 'ollama',
          url: 'http://localhost:11434',
          enabled: true,
          healthy: true,
          latency_ms: 18.0,
        },
        biohack: {
          name: 'biohack',
          url: 'http://localhost:8081',
          enabled: true,
          healthy: false,
          latency_ms: null,
          error: 'mock: service offline',
        },
      },
      resources: {
        cpu_percent: 23.5,
        memory: { total_gb: 16, available_gb: 9.2, percent: 42.5 },
        disk: { total_gb: 512, free_gb: 312, percent: 39.1 },
      },
    })
  ),

  http.get('/api/v1/health/services', () =>
    HttpResponse.json({
      services: {
        postgres: {
          name: 'postgres',
          url: 'postgresql://localhost:5432',
          enabled: true,
          healthy: true,
          latency_ms: 4.2,
        },
        redis: {
          name: 'redis',
          url: 'redis://localhost:6379',
          enabled: true,
          healthy: true,
          latency_ms: 1.1,
        },
      },
    })
  ),
]

// ---------------------------------------------------------------------------
// System (osascript)
// ---------------------------------------------------------------------------

const systemHandlers = [
  http.get('/api/v1/system/info', () =>
    HttpResponse.json({
      user_name: 'mock-user',
      computer_name: 'Micelia-Dev',
      cpu_type: 'Apple M-series (mock)',
      frontmost_app: 'Safari',
      dark_mode: true,
      volume: 35,
    })
  ),
  http.get('/api/v1/system/apps', () =>
    HttpResponse.json({
      apps: ['Safari', 'Code', 'Terminal', 'Notion', 'Spotify'],
      count: 5,
    })
  ),
  http.get('/api/v1/system/volume', () => HttpResponse.json({ volume: 35 })),
  http.get('/api/v1/system/dark-mode', () =>
    HttpResponse.json({ dark_mode: true })
  ),
  http.get('/api/v1/system/clipboard', () =>
    HttpResponse.json({ content: 'mock clipboard content' })
  ),
  http.post('/api/v1/system/notify', () =>
    HttpResponse.json({ success: true })
  ),
]

// ---------------------------------------------------------------------------
// AI
// ---------------------------------------------------------------------------

const aiHandlers = [
  http.get('/api/v1/ai/status', () =>
    HttpResponse.json({
      ollama: {
        available: true,
        models: ['llama3.2:3b', 'mistral:7b', 'qwen2.5:14b'],
      },
      codking: {
        available: false,
        cores: [],
      },
      compute_router: { enabled: true },
    })
  ),

  http.get('/api/v1/ai/models', () =>
    HttpResponse.json({ models: ['llama3.2:3b', 'mistral:7b', 'qwen2.5:14b'] })
  ),
]

// ---------------------------------------------------------------------------
// Energy
// ---------------------------------------------------------------------------

const energyHandlers = [
  http.get('/api/v1/energy/status', () =>
    HttpResponse.json({
      state: 'normal',
      battery_level: 78,
      is_charging: false,
      time_remaining_minutes: 240,
      solar_available: true,
      solar_watts: 120,
      is_online: true,
      power_source: 'battery',
      recommendations: [
        'Battery healthy: heavy tasks OK',
        'Solar producing: consider running ML jobs',
      ],
    })
  ),

  http.get('/api/v1/energy/history', () =>
    HttpResponse.json({ events: [] })
  ),

  http.get('/api/v1/energy/compute-recommendation', () =>
    HttpResponse.json({
      provider: 'ollama',
      reason: 'mock: battery > 50% and solar available',
    })
  ),
]

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

const mockEvents = [
  {
    event_id: 'evt-001',
    correlation_id: 'corr-aaa',
    timestamp: minutesAgo(2),
    category: 'health',
    subcategory: 'biomarker',
    source: 'biohack',
    action: 'create',
    event_type: 'biomarker.recorded',
    payload: { metric: 'hrv', value: 62 },
    metadata: {},
    tags: ['hrv', 'wearable'],
    compute_provider: null,
    compute_model: null,
    compute_latency_ms: null,
  },
  {
    event_id: 'evt-002',
    correlation_id: 'corr-bbb',
    timestamp: minutesAgo(15),
    category: 'system',
    subcategory: null,
    source: 'micelia',
    action: 'query',
    event_type: 'prompt.completed',
    payload: { prompt_id: 'prm-003' },
    metadata: {},
    tags: ['prompt'],
    compute_provider: 'ollama',
    compute_model: 'llama3.2:3b',
    compute_latency_ms: 1240,
  },
  {
    event_id: 'evt-003',
    correlation_id: null,
    timestamp: minutesAgo(45),
    category: 'research',
    subcategory: 'literature',
    source: 'canela',
    action: 'analyze',
    event_type: 'paper.indexed',
    payload: { title: 'Mock paper on longevity', doi: '10.0/mock' },
    metadata: {},
    tags: ['research'],
    compute_provider: null,
    compute_model: null,
    compute_latency_ms: null,
  },
]

const eventsHandlers = [
  http.get('/api/v1/events', ({ request }) => {
    const url = new URL(request.url)
    const limit = Number(url.searchParams.get('limit') ?? 50)
    const offset = Number(url.searchParams.get('offset') ?? 0)
    const category = url.searchParams.get('category')

    let filtered = mockEvents
    if (category) filtered = filtered.filter((e) => e.category === category)

    return HttpResponse.json({
      events: filtered.slice(offset, offset + limit),
      total: filtered.length,
      page: Math.floor(offset / limit) + 1,
      limit,
    })
  }),

  http.post('/api/v1/events', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>
    return HttpResponse.json(
      {
        event_id: `evt-${Math.random().toString(36).slice(2, 8)}`,
        status: 'created',
        timestamp: now(),
        ...body,
      },
      { status: 201 }
    )
  }),

  http.get('/api/v1/events/categories', () =>
    HttpResponse.json({
      categories: ['health', 'system', 'research', 'security', 'education'],
    })
  ),

  http.get('/api/v1/events/stats', () =>
    HttpResponse.json({
      total: mockEvents.length,
      by_category: { health: 1, system: 1, research: 1 },
    })
  ),
]

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------

const mockPrompts = [
  {
    prompt_id: 'prm-001',
    content: 'Resumir las novedades de Anthropic esta semana',
    category: 'short-term',
    priority: 2,
    status: 'pending',
    model_used: null,
    provider_used: null,
    prefer_paid: false,
    review_score: null,
    iterations: 0,
    output: null,
    error: null,
    created_at: minutesAgo(8),
    scheduled_at: null,
    processing_at: null,
    completed_at: null,
    parent_prompt_id: null,
    correlation_id: null,
    tags: ['news', 'ai'],
    metadata: {},
    source: 'manual',
    tokens_input: 0,
    tokens_output: 0,
    latency_ms: null,
    cost_usd: null,
  },
  {
    prompt_id: 'prm-002',
    content: 'Analizar mi HRV de los últimos 7 días',
    category: 'personal',
    priority: 3,
    status: 'queued',
    model_used: null,
    provider_used: null,
    prefer_paid: false,
    review_score: null,
    iterations: 0,
    output: null,
    error: null,
    created_at: minutesAgo(20),
    scheduled_at: null,
    processing_at: null,
    completed_at: null,
    parent_prompt_id: null,
    correlation_id: 'corr-aaa',
    tags: ['health'],
    metadata: {},
    source: 'note',
    tokens_input: 0,
    tokens_output: 0,
    latency_ms: null,
    cost_usd: null,
  },
  {
    prompt_id: 'prm-003',
    content: 'Plan de trabajo para mañana',
    category: 'plan',
    priority: 1,
    status: 'completed',
    model_used: 'llama3.2:3b',
    provider_used: 'ollama',
    prefer_paid: false,
    review_score: 0.87,
    iterations: 1,
    output: '1. Revisar PRs\n2. Sesión de QA Micelia\n3. Documentar T4.2',
    error: null,
    created_at: minutesAgo(60),
    scheduled_at: null,
    processing_at: minutesAgo(45),
    completed_at: minutesAgo(40),
    parent_prompt_id: null,
    correlation_id: 'corr-bbb',
    tags: ['planning'],
    metadata: {},
    source: 'manual',
    tokens_input: 320,
    tokens_output: 180,
    latency_ms: 1240,
    cost_usd: 0,
  },
]

const promptStats = {
  total: mockPrompts.length,
  by_status: { pending: 1, queued: 1, completed: 1 },
  by_category: { 'short-term': 1, personal: 1, plan: 1 },
  completed_today: 1,
  total_tokens_input: 320,
  total_tokens_output: 180,
  total_cost_usd: 0,
  avg_latency_ms: 1240,
}

const pipelineStatus = {
  agent: {
    running: true,
    last_scan: minutesAgo(1),
    pending_count: 1,
    interval_seconds: 60,
  },
  executor: {
    running: true,
    active_count: 1,
    completed_today: 1,
    failed_today: 0,
  },
}

const promptsHandlers = [
  http.get('/api/v1/prompts', ({ request }) => {
    const url = new URL(request.url)
    const status = url.searchParams.get('status')
    const category = url.searchParams.get('category')
    let filtered = mockPrompts
    if (status) filtered = filtered.filter((p) => p.status === status)
    if (category) filtered = filtered.filter((p) => p.category === category)
    return HttpResponse.json({
      prompts: filtered,
      count: filtered.length,
      limit: 50,
      offset: 0,
      total: filtered.length,
    })
  }),

  http.get('/api/v1/prompts/stats', () => HttpResponse.json(promptStats)),

  http.get('/api/v1/prompts/inbox', () =>
    HttpResponse.json({
      prompts: mockPrompts.filter((p) => p.status === 'pending'),
      count: 1,
      limit: 50,
      offset: 0,
      total: 1,
    })
  ),

  http.get('/api/v1/prompts/staging', () =>
    HttpResponse.json({
      prompts: mockPrompts.filter((p) => p.status === 'queued'),
      count: 1,
      limit: 50,
      offset: 0,
      total: 1,
    })
  ),

  http.get('/api/v1/prompts/archive', () =>
    HttpResponse.json({
      prompts: mockPrompts.filter((p) => p.status === 'completed'),
      count: 1,
      limit: 50,
      offset: 0,
      total: 1,
    })
  ),

  http.get('/api/v1/prompts/pipeline/status', () =>
    HttpResponse.json(pipelineStatus)
  ),

  http.get('/api/v1/prompts/lists', () =>
    HttpResponse.json({
      lists: [
        {
          list_id: 'lst-001',
          name: 'Rutinas diarias',
          slug: 'rutinas-diarias',
          description: 'Checks recurrentes cada mañana',
          category: 'routine',
          content_md: '- Revisar HRV\n- Hidratación\n- 10min meditación',
          is_active: true,
          created_at: minutesAgo(60 * 24 * 3),
          updated_at: null,
          metadata: {},
        },
      ],
      count: 1,
    })
  ),

  http.get('/api/v1/prompts/:id', ({ params }) => {
    const prompt = mockPrompts.find((p) => p.prompt_id === params.id)
    if (!prompt)
      return HttpResponse.json({ detail: 'not found' }, { status: 404 })
    return HttpResponse.json(prompt)
  }),

  http.post('/api/v1/prompts', async ({ request }) => {
    const body = (await request.json()) as { content?: string }
    return HttpResponse.json(
      {
        prompt_id: `prm-${Math.random().toString(36).slice(2, 8)}`,
        status: 'captured',
        content: body?.content ?? '',
      },
      { status: 201 }
    )
  }),

  http.post('/api/v1/prompts/notes', async ({ request }) => {
    const body = (await request.json()) as { text?: string }
    return HttpResponse.json(
      {
        prompt_id: `prm-${Math.random().toString(36).slice(2, 8)}`,
        status: 'captured',
        content: body?.text ?? '',
      },
      { status: 201 }
    )
  }),
]

// ---------------------------------------------------------------------------
// Dashboard summary
// ---------------------------------------------------------------------------

const dashboardHandlers = [
  http.get('/api/v1/dashboard/summary', () =>
    HttpResponse.json({
      timestamp: now(),
      activity: {
        captured_today: 7,
        processed_today: 5,
        failed_today: 0,
        pending: 1,
        queued: 1,
      },
      budget: {
        daily_spent: 0.42,
        daily_limit: 5.0,
        monthly_spent: 8.7,
        monthly_limit: 100.0,
      },
      queue_preview: mockPrompts
        .filter((p) => p.status !== 'completed')
        .map((p) => ({
          prompt_id: p.prompt_id,
          content: p.content,
          category: p.category,
          priority: p.priority,
          created_at: p.created_at,
        })),
      recent_results: mockPrompts
        .filter((p) => p.status === 'completed' && p.completed_at)
        .map((p) => ({
          prompt_id: p.prompt_id,
          content: p.content,
          provider_used: p.provider_used ?? 'unknown',
          model_used: p.model_used ?? 'unknown',
          latency_ms: p.latency_ms,
          cost_usd: p.cost_usd,
          completed_at: p.completed_at as string,
        })),
      agents: {
        agent_running: true,
        executor_running: true,
        scheduler_running: true,
        executor_active_count: 1,
      },
      calendar_upcoming: [
        {
          summary: 'QA manual Micelia (T4.2)',
          start: minutesAhead(60),
          end: minutesAhead(120),
        },
      ],
    })
  ),
]

// ---------------------------------------------------------------------------
// Calendar / Skills / MCP / Agents / Tunnel  (low-fidelity stubs)
// ---------------------------------------------------------------------------

const miscHandlers = [
  http.get('/api/v1/calendar/status', () =>
    HttpResponse.json({
      connected: false,
      calendars_count: 0,
      last_sync: null,
    })
  ),
  http.get('/api/v1/calendar/events', () => HttpResponse.json({ events: [] })),
  http.get('/api/v1/calendar/calendars', () =>
    HttpResponse.json({ calendars: [] })
  ),

  http.get('/api/v1/skills', () => HttpResponse.json({ skills: [], count: 0 })),

  http.get('/api/v1/mcp/servers', () =>
    HttpResponse.json({ servers: [], count: 0 })
  ),
  http.get('/api/v1/mcp/templates', () =>
    HttpResponse.json({ templates: ['python-fastmcp', 'node-mcp-sdk'] })
  ),

  http.get('/api/v1/agents/crews', () => HttpResponse.json({ crews: [] })),
  http.get('/api/v1/agents/workflows', () =>
    HttpResponse.json({ workflows: ['classify', 'execute', 'review'] })
  ),
  http.get('/api/v1/agents/runs', () => HttpResponse.json({ runs: [] })),

  http.get('/api/v1/tunnel/status', () =>
    HttpResponse.json({
      connected: false,
      public_url: null,
      started_at: null,
    })
  ),
]

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

export const handlers = [
  ...authHandlers,
  ...healthHandlers,
  ...systemHandlers,
  ...aiHandlers,
  ...energyHandlers,
  ...eventsHandlers,
  ...promptsHandlers,
  ...dashboardHandlers,
  ...miscHandlers,
]
