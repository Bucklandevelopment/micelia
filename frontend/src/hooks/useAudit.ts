import { useQuery } from '@tanstack/react-query'

interface AuditCheckpoint {
  timestamp: string
  agent: string
  action: string
  output_summary: string | null
}

interface AuditSession {
  session_id: string
  prompt_id: string
  workflow_name: string | null
  run_id: string | null
  started_at: string
  ended_at: string | null
  status: 'active' | 'completed' | 'failed'
  checkpoints: AuditCheckpoint[]
  metadata: Record<string, unknown>
  entire_session_id: string | null
}

interface AuditStatus {
  entire_available: boolean
  total_sessions: number
  active_sessions: number
}

const API_BASE = '/api/v1'

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('vital_access_token') : null
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`Audit API error: ${res.status}`)
  return res.json()
}

export function useAuditSessions(limit = 50) {
  return useQuery<{ sessions: AuditSession[]; total: number }>({
    queryKey: ['audit', 'sessions', limit],
    queryFn: () => fetchJson(`/audit/sessions?limit=${limit}`),
    refetchInterval: 15_000,
  })
}

export function useAuditSession(sessionId: string) {
  return useQuery<AuditSession>({
    queryKey: ['audit', 'session', sessionId],
    queryFn: () => fetchJson(`/audit/sessions/${sessionId}`),
    enabled: !!sessionId,
  })
}

export function usePromptAuditSessions(promptId: string) {
  return useQuery<{ prompt_id: string; sessions: AuditSession[] }>({
    queryKey: ['audit', 'prompt', promptId],
    queryFn: () => fetchJson(`/audit/prompts/${promptId}/sessions`),
    enabled: !!promptId,
  })
}

export function useAuditStatus() {
  return useQuery<AuditStatus>({
    queryKey: ['audit', 'status'],
    queryFn: () => fetchJson('/audit/status'),
    staleTime: 30_000,
  })
}

export type { AuditSession, AuditCheckpoint, AuditStatus }
