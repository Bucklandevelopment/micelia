// API Response Types for Micelia - Aligned with actual backend responses

// ============ Energy Types ============

export type EnergyState = 'abundant' | 'normal' | 'conserving' | 'critical' | 'survival'

// Backend response from /api/v1/energy/status
export interface EnergyStatusResponse {
  state: EnergyState
  battery_level: number
  is_charging: boolean
  time_remaining_minutes: number
  solar_available: boolean
  solar_watts: number
  is_online: boolean
  power_source: string
  recommendations: string[]
}

// Transformed energy data for UI components
export interface EnergyUIData {
  battery: {
    level: number
    is_charging: boolean
    time_remaining_minutes: number
  }
  solar: {
    available: boolean
    production_watts: number
  }
  network: {
    online: boolean
    type: string
  }
  state: EnergyState
  calculated: {
    estimated_runtime_hours: number
    energy_surplus: boolean
    can_run_heavy_tasks: boolean
  }
  recommendations: string[]
}

// ============ Health Types ============

export interface HealthCheckResponse {
  status: string
  timestamp: string
}

export interface ServiceHealthDetail {
  name: string
  url: string
  enabled: boolean
  healthy: boolean
  latency_ms: number | null
  error?: string
}

export interface HealthDetailedResponse {
  status: string
  timestamp: string
  uptime_seconds: number
  services: Record<string, ServiceHealthDetail>
  resources: {
    cpu_percent: number
    memory: {
      total_gb: number
      available_gb: number
      percent: number
    }
    disk: {
      total_gb: number
      free_gb: number
      percent: number
    }
  }
}

// ============ Events Types ============

export interface IdmEvent {
  event_id: string
  correlation_id: string | null
  timestamp: string
  category: string
  subcategory: string | null
  source: string
  action: string
  event_type: string
  payload: Record<string, unknown>
  metadata: Record<string, unknown>
  tags: string[]
  compute_provider: string | null
  compute_model: string | null
  compute_latency_ms: number | null
}

export interface IdmEventsResponse {
  events: IdmEvent[]
  total: number
  page: number
  limit: number
}

// ============ System Types ============

export interface SystemInfoResponse {
  user_name: string
  computer_name: string
  cpu_type: string
  frontmost_app: string
  dark_mode: boolean
  volume: number
}

// ============ AI Types ============

export interface AIStatusResponse {
  ollama: {
    available: boolean
    models: string[]
  }
  codking: {
    available: boolean
    cores: string[]
  }
  compute_router: {
    enabled: boolean
  }
}

// ============ Prompt Types ============

export type PromptStatus = 'captured' | 'classified' | 'staged' | 'pending' | 'queued' | 'processing' | 'completed' | 'failed' | 'reviewed' | 'archived' | 'draft'
export type PromptCategory = 'plan' | 'short-term' | 'work' | 'personal' | 'routine' | 'note' | 'project'

export interface Prompt {
  prompt_id: string
  content: string
  category: PromptCategory
  priority: number
  status: PromptStatus
  model_used: string | null
  provider_used: string | null
  prefer_paid: boolean
  review_score: number | null
  iterations: number
  output: string | null
  error: string | null
  created_at: string
  scheduled_at: string | null
  processing_at: string | null
  completed_at: string | null
  parent_prompt_id: string | null
  correlation_id: string | null
  tags: string[]
  metadata: Record<string, unknown>
  source: string
  tokens_input: number
  tokens_output: number
  latency_ms: number | null
  cost_usd: number | null
}

export interface PromptListResponse {
  prompts: Prompt[]
  count: number
  limit: number
  offset: number
  total: number
}

export interface PromptList {
  list_id: string
  name: string
  slug: string
  description: string | null
  category: string
  content_md: string
  is_active: boolean
  created_at: string
  updated_at: string | null
  metadata: Record<string, unknown>
}

export interface PipelineStatus {
  agent: {
    running: boolean
    last_scan: string | null
    pending_count: number
    interval_seconds: number
  }
  executor: {
    running: boolean
    active_count: number
    completed_today: number
    failed_today: number
  }
}

export interface PromptStats {
  total: number
  by_status: Record<string, number>
  by_category: Record<string, number>
  completed_today: number
  total_tokens_input: number
  total_tokens_output: number
  total_cost_usd: number
  avg_latency_ms: number
}

// ============ Service Status for UI ============

export interface ServiceStatus {
  name: string
  status: 'healthy' | 'unhealthy' | 'unknown'
  latency?: number
}

export interface SystemStatusData {
  services: ServiceStatus[]
  osascript: {
    enabled: boolean
    require_auth: boolean
  }
  ai: {
    models: string[]
  }
  resources?: {
    cpu_percent: number
    memory_percent: number
    disk_percent: number
  }
}
