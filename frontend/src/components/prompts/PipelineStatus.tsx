'use client'

import {
  Activity,
  Play,
  Pause,
  Clock,
  Loader2,
  CheckCircle,
  XCircle,
  Cpu,
} from 'lucide-react'
import { clsx } from 'clsx'
import { usePipelineStatus, usePipelineControl } from '@/hooks/usePrompts'

function formatLastScan(dateString: string | null): string {
  if (!dateString) return 'Never'
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then
  const seconds = Math.floor(diffMs / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  return new Date(dateString).toLocaleTimeString()
}

export function PipelineStatus() {
  const { data, isLoading } = usePipelineStatus()
  const { pause, resume } = usePipelineControl()

  const agentRunning = data?.agent?.running ?? false
  const executorRunning = data?.executor?.running ?? false
  const isPausing = pause.isPending
  const isResuming = resume.isPending

  const handleToggle = () => {
    if (agentRunning || executorRunning) {
      pause.mutate()
    } else {
      resume.mutate()
    }
  }

  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-idm-primary/10">
            <Activity className="w-5 h-5 text-idm-primary" />
          </div>
          <h2 className="text-sm font-semibold text-white">Pipeline</h2>
        </div>
        {isLoading && <Loader2 className="w-4 h-4 text-gray-500 animate-spin" />}
      </div>

      <div className="space-y-3">
        {/* Agent status */}
        <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Agent
            </span>
            <span
              className={clsx(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium',
                agentRunning
                  ? 'bg-energy-abundant/15 text-energy-abundant'
                  : 'bg-gray-500/15 text-gray-400'
              )}
            >
              <span
                className={clsx(
                  'w-1.5 h-1.5 rounded-full',
                  agentRunning ? 'bg-energy-abundant animate-pulse' : 'bg-gray-500'
                )}
              />
              {agentRunning ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-1.5 text-gray-400">
              <Clock className="w-3 h-3" />
              <span>Last scan: {formatLastScan(data?.agent?.last_scan ?? null)}</span>
            </div>
            <div className="flex items-center gap-1.5 text-gray-400">
              <Loader2 className="w-3 h-3" />
              <span>Pending: {data?.agent?.pending_count ?? 0}</span>
            </div>
          </div>
        </div>

        {/* Executor status */}
        <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
              Executor
            </span>
            <span
              className={clsx(
                'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium',
                executorRunning
                  ? 'bg-energy-abundant/15 text-energy-abundant'
                  : 'bg-gray-500/15 text-gray-400'
              )}
            >
              <span
                className={clsx(
                  'w-1.5 h-1.5 rounded-full',
                  executorRunning ? 'bg-energy-abundant animate-pulse' : 'bg-gray-500'
                )}
              />
              {executorRunning ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="flex items-center gap-1.5 text-gray-400">
              <Cpu className="w-3 h-3" />
              <span>Active: {data?.executor?.active_count ?? 0}</span>
            </div>
            <div className="flex items-center gap-1.5 text-energy-abundant">
              <CheckCircle className="w-3 h-3" />
              <span>{data?.executor?.completed_today ?? 0} done</span>
            </div>
            <div className="flex items-center gap-1.5 text-energy-critical">
              <XCircle className="w-3 h-3" />
              <span>{data?.executor?.failed_today ?? 0} fail</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pause / Resume button */}
      <button
        type="button"
        onClick={handleToggle}
        disabled={isPausing || isResuming}
        className={clsx(
          'w-full mt-4 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200',
          agentRunning || executorRunning
            ? 'bg-energy-conserving/15 text-energy-conserving border border-energy-conserving/30 hover:bg-energy-conserving/25'
            : 'bg-energy-abundant/15 text-energy-abundant border border-energy-abundant/30 hover:bg-energy-abundant/25',
          'disabled:opacity-50 disabled:cursor-not-allowed'
        )}
      >
        {isPausing || isResuming ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : agentRunning || executorRunning ? (
          <Pause className="w-4 h-4" />
        ) : (
          <Play className="w-4 h-4" />
        )}
        {isPausing ? 'Pausing...' : isResuming ? 'Resuming...' : agentRunning || executorRunning ? 'Pause Pipeline' : 'Resume Pipeline'}
      </button>
    </div>
  )
}
