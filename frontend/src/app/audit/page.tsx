'use client'

import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { useAuditSessions, useAuditStatus, type AuditSession, type AuditCheckpoint } from '@/hooks/useAudit'
import {
  ShieldCheck,
  CheckCircle,
  XCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Terminal,
  Wifi,
  WifiOff,
} from 'lucide-react'

const statusConfig: Record<string, { color: string; bg: string; icon: typeof CheckCircle }> = {
  active: { color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Loader2 },
  completed: { color: 'text-green-400', bg: 'bg-green-500/10', icon: CheckCircle },
  failed: { color: 'text-red-400', bg: 'bg-red-500/10', icon: XCircle },
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleDateString('es-ES', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

function SessionRow({ session }: { session: AuditSession }) {
  const [expanded, setExpanded] = useState(false)
  const config = statusConfig[session.status] ?? statusConfig.completed
  const StatusIcon = config.icon

  return (
    <div className="glass rounded-xl border border-idm-border overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-4 hover:bg-idm-surface/30 transition-colors text-left"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-gray-500 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-500 shrink-0" />
        )}

        <StatusIcon
          className={`w-4 h-4 ${config.color} shrink-0 ${session.status === 'active' ? 'animate-spin' : ''}`}
        />

        <span className={`text-xs px-1.5 py-0.5 rounded ${config.bg} ${config.color}`}>
          {session.status}
        </span>

        {session.workflow_name && (
          <span className="text-xs text-gray-300 font-medium">{session.workflow_name}</span>
        )}

        <span className="text-[10px] text-gray-600 font-mono">
          {session.prompt_id.slice(0, 8)}...
        </span>

        <span className="text-xs text-gray-500 ml-auto">
          {session.checkpoints.length} steps
        </span>

        <span className="text-xs text-gray-600">{formatDate(session.started_at)}</span>
      </button>

      {expanded && (
        <div className="border-t border-idm-border/50 p-4 bg-idm-surface/20">
          <div className="grid grid-cols-2 gap-3 mb-4 text-xs">
            <div>
              <span className="text-gray-500">Session ID: </span>
              <span className="text-gray-400 font-mono">{session.session_id.slice(0, 12)}...</span>
            </div>
            <div>
              <span className="text-gray-500">Run ID: </span>
              <span className="text-gray-400 font-mono">{session.run_id?.slice(0, 12) ?? 'N/A'}...</span>
            </div>
            <div>
              <span className="text-gray-500">Started: </span>
              <span className="text-gray-400">{formatDate(session.started_at)}</span>
            </div>
            <div>
              <span className="text-gray-500">Ended: </span>
              <span className="text-gray-400">{session.ended_at ? formatDate(session.ended_at) : 'Running'}</span>
            </div>
          </div>

          {session.checkpoints.length > 0 && (
            <div className="space-y-1">
              <h4 className="text-xs text-gray-500 mb-2">Checkpoints</h4>
              {session.checkpoints.map((cp: AuditCheckpoint, i: number) => (
                <div key={i} className="flex items-start gap-3 ml-2">
                  <div className="flex flex-col items-center">
                    <div className="w-2 h-2 rounded-full bg-idm-primary mt-1.5" />
                    {i < session.checkpoints.length - 1 && (
                      <div className="w-px flex-1 bg-idm-border min-h-[16px]" />
                    )}
                  </div>
                  <div className="pb-2 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-300">{cp.agent}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-idm-surface text-gray-500">
                        {cp.action}
                      </span>
                      <span className="text-[10px] text-gray-700 ml-auto">{formatTime(cp.timestamp)}</span>
                    </div>
                    {cp.output_summary && (
                      <p className="text-[10px] text-gray-600 mt-0.5 line-clamp-2">{cp.output_summary}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function AuditPage() {
  const { data: sessionsData, isLoading } = useAuditSessions(100)
  const { data: status } = useAuditStatus()
  const [filter, setFilter] = useState<string>('all')

  const sessions = sessionsData?.sessions ?? []
  const filtered = filter === 'all' ? sessions : sessions.filter((s) => s.status === filter)

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ShieldCheck className="w-6 h-6 text-amber-400" />
            <div>
              <h2 className="text-lg font-semibold text-white">Audit Trail</h2>
              <p className="text-xs text-gray-500">
                Workflow session traceability
              </p>
            </div>
          </div>

          {/* Entire CLI status */}
          {status && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-idm-surface border border-idm-border">
              {status.entire_available ? (
                <>
                  <Wifi className="w-3.5 h-3.5 text-green-400" />
                  <span className="text-xs text-green-400">entire CLI</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3.5 h-3.5 text-gray-600" />
                  <span className="text-xs text-gray-600">in-memory only</span>
                </>
              )}
              <span className="text-xs text-gray-500 ml-2">
                {status.total_sessions} sessions
              </span>
            </div>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex items-center gap-2">
          {['all', 'active', 'completed', 'failed'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs transition-colors ${
                filter === f
                  ? 'bg-idm-primary/20 text-idm-primary border border-idm-primary/30'
                  : 'bg-idm-surface/50 text-gray-500 border border-idm-border/50 hover:text-gray-300'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
              {f !== 'all' && (
                <span className="ml-1 text-[10px]">
                  ({sessions.filter((s) => s.status === f).length})
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Sessions list */}
        {isLoading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-16 rounded-xl bg-idm-surface animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <Terminal className="w-12 h-12 text-gray-700 mx-auto mb-3" />
            <p className="text-gray-500">No audit sessions recorded yet</p>
            <p className="text-xs text-gray-600 mt-1">
              Sessions are created when workflows execute prompts
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((session) => (
              <SessionRow key={session.session_id} session={session} />
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
