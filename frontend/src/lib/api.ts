// API Client for Micelia - Aligned with backend responses
import type {
  EnergyStatusResponse,
  EnergyUIData,
  EnergyState,
  HealthCheckResponse,
  HealthDetailedResponse,
  IdmEvent,
  IdmEventsResponse,
  EventStatsResponse,
  SystemInfoResponse,
  AIStatusResponse,
  Prompt,
  PromptListResponse,
  PromptList,
  PipelineStatus,
  PromptStats,
} from '@/types/api'

const API_BASE = '/api/v1'

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

// ============ Token Management ============

let accessToken: string | null = null

function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null
  if (accessToken) return accessToken
  return localStorage.getItem('vital_access_token')
}

function setStoredTokens(access: string, refresh: string): void {
  localStorage.setItem('vital_access_token', access)
  localStorage.setItem('vital_refresh_token', refresh)
  // Also set cookie for middleware
  document.cookie = `vital_auth=${access}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`
  accessToken = access
}

function clearStoredTokens(): void {
  localStorage.removeItem('vital_access_token')
  localStorage.removeItem('vital_refresh_token')
  document.cookie = 'vital_auth=; path=/; max-age=0'
  accessToken = null
}

async function tryRefreshToken(): Promise<boolean> {
  const refresh = localStorage.getItem('vital_refresh_token')
  if (!refresh) return false
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) return false
    const data = await res.json()
    setStoredTokens(data.access_token, data.refresh_token)
    return true
  } catch { return false }
}

// ============ Core Fetch ============

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  const token = getStoredToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (response.status === 401) {
    const refreshed = await tryRefreshToken()
    if (refreshed) {
      const retryHeaders: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(options.headers as Record<string, string>),
        'Authorization': `Bearer ${getStoredToken()}`,
      }
      const retry = await fetch(url, { ...options, headers: retryHeaders })
      if (!retry.ok) {
        throw new ApiError(retry.status, `API Error: ${retry.statusText}`)
      }
      return retry.json()
    }
    // Refresh failed — redirect to login
    if (typeof window !== 'undefined') {
      clearStoredTokens()
      window.location.href = '/login'
    }
    throw new ApiError(401, 'Authentication required')
  }

  if (!response.ok) {
    throw new ApiError(response.status, `API Error: ${response.statusText}`)
  }

  return response.json()
}

// ============ Energy API ============

// Transform backend energy response to UI-friendly format
function transformEnergyStatus(data: EnergyStatusResponse): EnergyUIData {
  const runtimeHours = data.time_remaining_minutes > 0
    ? data.time_remaining_minutes / 60
    : (data.is_charging ? Infinity : 0)

  return {
    battery: {
      level: data.battery_level,
      is_charging: data.is_charging,
      time_remaining_minutes: data.time_remaining_minutes,
    },
    solar: {
      available: data.solar_available,
      production_watts: data.solar_watts,
    },
    network: {
      online: data.is_online,
      type: data.power_source,
    },
    state: data.state,
    calculated: {
      estimated_runtime_hours: runtimeHours,
      energy_surplus: data.solar_watts > 0 && data.is_charging,
      can_run_heavy_tasks: data.battery_level > 50 || data.is_charging,
    },
    recommendations: data.recommendations,
  }
}

export const energyApi = {
  // Get raw energy status from backend
  getStatusRaw: () => fetchApi<EnergyStatusResponse>('/energy/status'),

  // Get transformed energy status for UI components
  getStatus: async (): Promise<EnergyUIData> => {
    const data = await fetchApi<EnergyStatusResponse>('/energy/status')
    return transformEnergyStatus(data)
  },

  // Get energy state (uses same endpoint, extracts state)
  getState: async () => {
    const data = await fetchApi<EnergyStatusResponse>('/energy/status')
    return {
      current_state: data.state,
      recommendations: data.recommendations
    }
  },

  // Get energy history
  getHistory: (hours = 24) =>
    fetchApi<{ events: unknown[] }>(`/energy/history?hours=${hours}`),

  // Get compute recommendation
  getComputeRecommendation: () =>
    fetchApi<{ provider: string; reason: string }>('/energy/compute-recommendation'),
}

// ============ Health API ============

export const healthApi = {
  check: () => fetchApi<HealthCheckResponse>('/health'),

  detailed: () => fetchApi<HealthDetailedResponse>('/health/detailed'),

  services: () => fetchApi<{ services: Record<string, unknown> }>('/health/services'),

  live: () => fetchApi<{ status: string }>('/health/live'),

  ready: () => fetchApi<{ status: string }>('/health/ready'),
}

// ============ Events API ============

export const eventsApi = {
  list: (params?: { category?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.category) searchParams.set('category', params.category)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<IdmEventsResponse>(`/events${query ? `?${query}` : ''}`)
  },

  getById: async (id: string): Promise<IdmEvent> => {
    // Backend uses event_id in the list response
    // For single event, we fetch the list and filter
    const response = await fetchApi<IdmEventsResponse>(`/events?limit=100`)
    const event = response.events.find(e => e.event_id === id)
    if (!event) {
      throw new ApiError(404, 'Event not found')
    }
    return event
  },

  categories: () => fetchApi<{ categories: string[] }>('/events/categories'),

  stats: () => fetchApi<EventStatsResponse>('/events/stats'),

  timeline: (date: string) =>
    fetchApi<{ events: IdmEvent[] }>(`/events/timeline/${date}`),

  byCorrelation: (correlationId: string) =>
    fetchApi<{ events: IdmEvent[] }>(`/events/by-correlation/${correlationId}`),
}

// ============ System API (OSASCRIPT) ============

export const systemApi = {
  info: (apiKey?: string) => {
    const headers: Record<string, string> = {}
    if (apiKey) headers['X-API-Key'] = apiKey
    return fetchApi<SystemInfoResponse>('/system/info', { headers })
  },

  apps: (apiKey?: string) => {
    const headers: Record<string, string> = {}
    if (apiKey) headers['X-API-Key'] = apiKey
    return fetchApi<{ apps: string[]; count: number }>('/system/apps', { headers })
  },

  volume: (apiKey?: string) => {
    const headers: Record<string, string> = {}
    if (apiKey) headers['X-API-Key'] = apiKey
    return fetchApi<{ volume: number }>('/system/volume', { headers })
  },

  darkMode: (apiKey?: string) => {
    const headers: Record<string, string> = {}
    if (apiKey) headers['X-API-Key'] = apiKey
    return fetchApi<{ dark_mode: boolean }>('/system/dark-mode', { headers })
  },

  clipboard: (apiKey?: string) => {
    const headers: Record<string, string> = {}
    if (apiKey) headers['X-API-Key'] = apiKey
    return fetchApi<{ content: string }>('/system/clipboard', { headers })
  },

  notify: (title: string, message: string, apiKey?: string) => {
    const headers: Record<string, string> = {}
    if (apiKey) headers['X-API-Key'] = apiKey
    return fetchApi<{ success: boolean }>('/system/notify', {
      method: 'POST',
      headers,
      body: JSON.stringify({ title, message }),
    })
  },
}

// ============ AI API ============

export const aiApi = {
  status: () => fetchApi<AIStatusResponse>('/ai/status'),

  models: () => fetchApi<{ models: string[] }>('/ai/models'),

  chat: (model: string, messages: { role: string; content: string }[]) =>
    fetchApi<{ response: string; model: string }>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ model, messages }),
    }),

  embeddings: (model: string, text: string) =>
    fetchApi<{ embeddings: number[] }>('/ai/embeddings', {
      method: 'POST',
      body: JSON.stringify({ model, text }),
    }),
}

// ============ Prompts API ============

export const promptsApi = {
  list: (params?: { status?: string; category?: string; source?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set('status', params.status)
    if (params?.category) searchParams.set('category', params.category)
    if (params?.source) searchParams.set('source', params.source)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    const query = searchParams.toString()
    return fetchApi<PromptListResponse>(`/prompts${query ? `?${query}` : ''}`)
  },

  get: (id: string) => fetchApi<Prompt>(`/prompts/${id}`),

  create: (data: { content: string; category?: string; priority?: number; tags?: string[]; scheduled_at?: string; prefer_paid?: boolean }) =>
    fetchApi<{ prompt_id: string; status: string }>('/prompts', { method: 'POST', body: JSON.stringify(data) }),

  update: (id: string, data: Partial<Prompt>) =>
    fetchApi<{ success: boolean }>(`/prompts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  delete: (id: string) =>
    fetchApi<{ success: boolean }>(`/prompts/${id}`, { method: 'DELETE' }),

  retry: (id: string) =>
    fetchApi<{ success: boolean; status: string }>(`/prompts/${id}/retry`, { method: 'POST' }),

  createNote: (text: string, tags?: string[]) =>
    fetchApi<{ prompt_id: string; status: string }>('/prompts/notes', { method: 'POST', body: JSON.stringify({ text, tags }) }),

  stats: () => fetchApi<PromptStats>('/prompts/stats'),

  // ---- Panel-specific endpoints ----

  getInbox: () => fetchApi<PromptListResponse>('/prompts/inbox'),

  getStaging: () => fetchApi<PromptListResponse>('/prompts/staging'),

  getArchived: (params?: { limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    const query = searchParams.toString()
    return fetchApi<PromptListResponse>(`/prompts/archive${query ? `?${query}` : ''}`)
  },

  classifyPrompt: (id: string, data: { category?: string; tags?: string[] }) =>
    fetchApi<{ success: boolean; status: string }>(`/prompts/${id}/classify`, { method: 'POST', body: JSON.stringify(data) }),

  stagePrompt: (id: string) =>
    fetchApi<{ success: boolean; status: string }>(`/prompts/${id}/stage`, { method: 'POST' }),

  approvePrompt: (id: string) =>
    fetchApi<{ success: boolean; status: string }>(`/prompts/${id}/approve`, { method: 'POST' }),

  archivePrompt: (id: string) =>
    fetchApi<{ success: boolean }>(`/prompts/${id}/archive`, { method: 'POST' }),

  promoteToList: (id: string, slug: string) =>
    fetchApi<{ success: boolean }>(`/prompts/${id}/promote/list`, { method: 'POST', body: JSON.stringify({ slug }) }),

  promoteToSkill: (id: string, data: { name: string; trigger_pattern: string }) =>
    fetchApi<{ success: boolean; skill_id: string }>(`/prompts/${id}/promote/skill`, { method: 'POST', body: JSON.stringify(data) }),

  // ---- Lists ----

  listLists: () => fetchApi<{ lists: PromptList[]; count: number }>('/prompts/lists'),

  getList: (slug: string) => fetchApi<PromptList>(`/prompts/lists/${slug}`),

  createList: (data: { name: string; description?: string; category?: string; content_md?: string }) =>
    fetchApi<{ list_id: string }>('/prompts/lists', { method: 'POST', body: JSON.stringify(data) }),

  updateList: (slug: string, data: { description?: string; content_md?: string; is_active?: boolean }) =>
    fetchApi<{ success: boolean }>(`/prompts/lists/${slug}`, { method: 'PATCH', body: JSON.stringify(data) }),

  deleteList: (slug: string) =>
    fetchApi<{ success: boolean }>(`/prompts/lists/${slug}`, { method: 'DELETE' }),

  // ---- Pipeline ----

  pipelineStatus: () => fetchApi<PipelineStatus>('/prompts/pipeline/status'),

  pipelinePause: () => fetchApi<{ success: boolean; status: string }>('/prompts/pipeline/pause', { method: 'POST' }),

  pipelineResume: () => fetchApi<{ success: boolean; status: string }>('/prompts/pipeline/resume', { method: 'POST' }),
}

// ============ Tunnel API ============

export interface TunnelStatus {
  connected: boolean
  public_url: string | null
  started_at: string | null
  tunnels_count?: number
}

export const tunnelApi = {
  status: () => fetchApi<TunnelStatus>('/tunnel/status'),
  start: (port?: number) =>
    fetchApi<{ success: boolean; public_url?: string; message?: string }>('/tunnel/start', {
      method: 'POST',
      body: JSON.stringify(port ? { port } : {}),
    }),
  stop: () =>
    fetchApi<{ success: boolean; message: string }>('/tunnel/stop', { method: 'POST' }),
  info: () => fetchApi<TunnelStatus>('/tunnel/info'),
}

// ============ Calendar API ============

export interface CalendarStatus {
  connected: boolean
  calendars_count?: number
  last_sync?: string | null
}

export const calendarApi = {
  status: () => fetchApi<CalendarStatus>('/calendar/status'),
  getAuthUrl: () => fetchApi<{ auth_url: string }>('/calendar/auth'),
  callback: (code: string) =>
    fetchApi<{ success: boolean }>(`/calendar/callback?code=${encodeURIComponent(code)}`),
  calendars: () => fetchApi<{ calendars: unknown[] }>('/calendar/calendars'),
  events: (date?: string) => {
    const q = date ? `?date=${date}` : ''
    return fetchApi<{ events: unknown[] }>(`/calendar/events${q}`)
  },
  createEvent: (data: { summary: string; start: string; end: string; description?: string }) =>
    fetchApi<{ event_id: string }>('/calendar/events', { method: 'POST', body: JSON.stringify(data) }),
  sync: () => fetchApi<{ synced: number }>('/calendar/sync', { method: 'POST' }),
  disconnect: () => fetchApi<{ success: boolean }>('/calendar/disconnect', { method: 'DELETE' }),
}

// ============ Skills API ============

export interface Skill {
  skill_id: string
  name: string
  slug: string
  description: string
  trigger_pattern: string
  prompt_template: string
  is_active: boolean
  usage_count: number
  created_at: string
  updated_at: string | null
}

export const skillsApi = {
  list: () => fetchApi<{ skills: Skill[]; count: number }>('/skills'),
  get: (slug: string) => fetchApi<Skill>(`/skills/${slug}`),
  create: (data: { name: string; description: string; trigger_pattern: string; prompt_template: string }) =>
    fetchApi<{ skill_id: string }>('/skills', { method: 'POST', body: JSON.stringify(data) }),
  update: (slug: string, data: Partial<Skill>) =>
    fetchApi<{ success: boolean }>(`/skills/${slug}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (slug: string) =>
    fetchApi<{ success: boolean }>(`/skills/${slug}`, { method: 'DELETE' }),
  toggle: (slug: string) =>
    fetchApi<{ is_active: boolean }>(`/skills/${slug}/toggle`, { method: 'POST' }),
  test: (slug: string, prompt: string) =>
    fetchApi<{ result: string }>(`/skills/${slug}/test`, { method: 'POST', body: JSON.stringify({ prompt }) }),
}

// ============ MCP API ============

export interface MCPServer {
  server_id: string
  name: string
  description: string
  language: string
  tools: { name: string; description: string }[]
  status: 'stopped' | 'running'
  created_at: string
}

export const mcpApi = {
  servers: () => fetchApi<{ servers: MCPServer[]; count: number }>('/mcp/servers'),
  get: (id: string) => fetchApi<MCPServer & { source_code: string }>(`/mcp/servers/${id}`),
  generate: (data: { name: string; description: string; tools: { name: string; description: string; parameters?: Record<string, unknown> }[]; language?: string }) =>
    fetchApi<{ server_id: string; path: string }>('/mcp/generate', { method: 'POST', body: JSON.stringify(data) }),
  delete: (id: string) =>
    fetchApi<{ success: boolean }>(`/mcp/servers/${id}`, { method: 'DELETE' }),
  start: (id: string) =>
    fetchApi<{ success: boolean }>(`/mcp/servers/${id}/start`, { method: 'POST' }),
  stop: (id: string) =>
    fetchApi<{ success: boolean }>(`/mcp/servers/${id}/stop`, { method: 'POST' }),
  templates: () => fetchApi<{ templates: string[] }>('/mcp/templates'),
  fromPrompt: (promptId: string) =>
    fetchApi<{ server_id: string }>('/mcp/from-prompt', { method: 'POST', body: JSON.stringify({ prompt_id: promptId }) }),
}

// ============ Agents API ============

export interface AgentCrew {
  crew_id: string
  name: string
  agents: string[]
  workflow: string
  created_at: string
}

export interface AgentRun {
  run_id: string
  prompt_id: string
  workflow: string
  status: 'running' | 'completed' | 'failed'
  steps: { agent: string; status: string; output?: string; duration_ms?: number }[]
  started_at: string
  completed_at: string | null
}

export const agentsApi = {
  crews: () => fetchApi<{ crews: AgentCrew[] }>('/agents/crews'),
  createCrew: (data: { name: string; agents: string[]; workflow: string }) =>
    fetchApi<{ crew_id: string }>('/agents/crews', { method: 'POST', body: JSON.stringify(data) }),
  workflows: () => fetchApi<{ workflows: string[] }>('/agents/workflows'),
  execute: (data: { prompt_id: string; workflow?: string }) =>
    fetchApi<{ run_id: string }>('/agents/execute', { method: 'POST', body: JSON.stringify(data) }),
  runs: () => fetchApi<{ runs: AgentRun[] }>('/agents/runs'),
  getRun: (id: string) => fetchApi<AgentRun>(`/agents/runs/${id}`),
}

// ============ Auth API ============

export const authApi = {
  login: async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) throw new ApiError(res.status, 'Invalid credentials')
    const data = await res.json()
    setStoredTokens(data.access_token, data.refresh_token)
    return data
  },
  register: async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) {
      const message =
        res.status === 409
          ? 'Email already registered'
          : res.status === 422
            ? 'Invalid email or password (min. 8 characters)'
            : 'Registration failed'
      throw new ApiError(res.status, message)
    }
    const data = await res.json()
    setStoredTokens(data.access_token, data.refresh_token)
    return data
  },
  me: () => fetchApi<{ username: string; auth_method: string }>('/auth/me'),
  logout: () => { clearStoredTokens() },
}

export { ApiError }
