'use client'

import { usePromptAuditSessions, type AuditSession, type AuditCheckpoint } from '@/hooks/useAudit'
import { ShieldCheck, CheckCircle, XCircle, Loader2 } from 'lucide-react'

const statusConfig = {
  active: { color: 'text-blue-400', bg: 'bg-blue-500/10', icon: Loader2 },
  completed: { color: 'text-green-400', bg: 'bg-green-500/10', icon: CheckCircle },
  failed: { color: 'text-red-400', bg: 'bg-red-500/10', icon: XCircle },
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return iso.slice(11, 19)
  }
}

function CheckpointNode({ cp }: { cp: AuditCheckpoint }) {
  return (
    <div className="flex gap-3 ml-3">
      <div className="flex flex-col items-center">
        <div className="w-2 h-2 rounded-full bg-idm-primary mt-1.5" />
        <div className="w-px flex-1 bg-idm-border" />
      </div>
      <div className="pb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-300">{cp.agent}</span>
          <span className="text-[10px] text-gray-600">{cp.action}</span>
          <span className="text-[10px] text-gray-700 ml-auto">{formatTime(cp.timestamp)}</span>
        </div>
        {cp.output_summary && (
          <p className="text-[10px] text-gray-500 mt-0.5 truncate max-w-xs">{cp.output_summary}</p>
        )}
      </div>
    </div>
  )
}

function SessionCard({ session }: { session: AuditSession }) {
  const { color, bg, icon: StatusIcon } = statusConfig[session.status] ?? statusConfig.completed

  return (
    <div className="rounded-lg bg-idm-surface/50 border border-idm-border/50 p-3">
      <div className="flex items-center gap-2 mb-2">
        <StatusIcon className={`w-3.5 h-3.5 ${color} ${session.status === 'active' ? 'animate-spin' : ''}`} />
        <span className={`text-[10px] px-1.5 py-0.5 rounded ${bg} ${color}`}>{session.status}</span>
        {session.workflow_name && (
          <span className="text-[10px] text-gray-500">{session.workflow_name}</span>
        )}
        <span className="text-[10px] text-gray-700 ml-auto">{formatTime(session.started_at)}</span>
      </div>

      {session.checkpoints.length > 0 && (
        <div className="mt-2">
          {session.checkpoints.map((cp, i) => (
            <CheckpointNode key={i} cp={cp} />
          ))}
        </div>
      )}
    </div>
  )
}

export function AuditTrail({ promptId }: { promptId: string }) {
  const { data, isLoading } = usePromptAuditSessions(promptId)
  const sessions = data?.sessions ?? []

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-2">
        <div className="h-4 w-20 bg-idm-surface rounded" />
        <div className="h-16 bg-idm-surface rounded" />
      </div>
    )
  }

  if (sessions.length === 0) {
    return null
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-gray-400 mb-2 flex items-center gap-1.5">
        <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
        Audit Trail ({sessions.length})
      </h4>
      <div className="space-y-2">
        {sessions.map((session) => (
          <SessionCard key={session.session_id} session={session} />
        ))}
      </div>
    </div>
  )
}
