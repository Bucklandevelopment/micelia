'use client'

import { Bot } from 'lucide-react'

interface AgentStatus {
  agent_running: boolean
  executor_running: boolean
  scheduler_running: boolean
  executor_active_count: number
}

function StatusDot({ active, label, detail }: { active: boolean; label: string; detail?: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${active ? 'bg-green-400 shadow-green-400/50 shadow-sm' : 'bg-gray-600'}`} />
      <span className="text-xs text-gray-300">{label}</span>
      {detail && <span className="text-[10px] text-gray-600 ml-auto">{detail}</span>}
    </div>
  )
}

export function AgentStatusCard({ data }: { data?: AgentStatus }) {
  const d = data ?? { agent_running: false, executor_running: false, scheduler_running: false, executor_active_count: 0 }

  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-1.5">
        <Bot className="w-4 h-4 text-pink-400" />
        Agents
      </h3>
      <div className="space-y-2">
        <StatusDot active={d.agent_running} label="Prioritizer" detail="5s loop" />
        <StatusDot
          active={d.executor_running}
          label="Executor"
          detail={d.executor_active_count > 0 ? `${d.executor_active_count} active` : undefined}
        />
        <StatusDot active={d.scheduler_running} label="Scheduler" detail="60s loop" />
      </div>
    </div>
  )
}
