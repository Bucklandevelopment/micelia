import { useQuery } from '@tanstack/react-query'

interface DashboardSummary {
  timestamp: string
  activity: {
    captured_today: number
    processed_today: number
    failed_today: number
    pending: number
    queued: number
  }
  budget: {
    daily_spent: number
    daily_limit: number
    monthly_spent: number
    monthly_limit: number
  }
  queue_preview: Array<{
    prompt_id: string
    content: string
    category: string
    priority: number
    created_at: string
  }>
  recent_results: Array<{
    prompt_id: string
    content: string
    provider_used: string
    model_used: string
    latency_ms: number | null
    cost_usd: number | null
    completed_at: string
  }>
  agents: {
    agent_running: boolean
    executor_running: boolean
    scheduler_running: boolean
    executor_active_count: number
  }
  calendar_upcoming: Array<{
    summary: string
    start: string
    end: string
  }>
}

const API_BASE = '/api/v1'

async function fetchDashboard(): Promise<DashboardSummary> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('vital_access_token') : null
  const res = await fetch(`${API_BASE}/dashboard/summary`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`)
  return res.json()
}

export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: ['dashboard', 'summary'],
    queryFn: fetchDashboard,
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

export type { DashboardSummary }
