'use client'

import { Header } from '@/components/layout/Header'
import { usePrompts } from '@/hooks/usePrompts'
import { usePipelineStatus } from '@/hooks/usePrompts'
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  ArrowRight,
  Cpu,
  Zap,
  BarChart3,
} from 'lucide-react'

export default function MonitorPage() {
  const { data: completedData } = usePrompts({ status: 'completed', limit: 20 })
  const { data: failedData } = usePrompts({ status: 'failed', limit: 20 })
  const { data: pipelineStatus } = usePipelineStatus()

  const completedPrompts = completedData?.prompts ?? []
  const failedPrompts = failedData?.prompts ?? []

  // Merge and sort activity log by completed_at descending
  const activityLog = [...completedPrompts, ...failedPrompts]
    .sort((a, b) => {
      const dateA = a.completed_at ?? a.created_at
      const dateB = b.completed_at ?? b.created_at
      return new Date(dateB).getTime() - new Date(dateA).getTime()
    })
    .slice(0, 20)

  // Compute model usage stats from completed prompts
  const providerCounts: Record<string, number> = {}
  for (const p of completedPrompts) {
    const provider = p.provider_used ?? 'unknown'
    providerCounts[provider] = (providerCounts[provider] ?? 0) + 1
  }
  const providerEntries = Object.entries(providerCounts).sort(
    (a, b) => b[1] - a[1]
  )

  const agent = pipelineStatus?.agent
  const executor = pipelineStatus?.executor

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Pipeline Visualization */}
        <div className="glass rounded-xl p-6 border border-idm-border">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Cpu className="w-5 h-5 text-yellow-400" />
            Pipeline Flow
          </h2>
          <div className="flex items-center justify-center gap-3 flex-wrap">
            {/* Ingestion */}
            <div className="flex flex-col items-center gap-1">
              <div className="px-4 py-3 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-400 text-sm font-medium min-w-[100px] text-center">
                Ingestion
              </div>
              <span className="text-xs text-gray-600">Notes + API</span>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-600 shrink-0" />

            {/* Queue */}
            <div className="flex flex-col items-center gap-1">
              <div className="px-4 py-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm font-medium min-w-[100px] text-center">
                Queue
                {agent && (
                  <span className="block text-xs text-yellow-600 mt-0.5">
                    {agent.pending_count} pending
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-600">Priority sort</span>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-600 shrink-0" />

            {/* Router */}
            <div className="flex flex-col items-center gap-1">
              <div className="px-4 py-3 rounded-lg bg-purple-500/10 border border-purple-500/30 text-purple-400 text-sm font-medium min-w-[100px] text-center">
                Router
              </div>
              <span className="text-xs text-gray-600">Model select</span>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-600 shrink-0" />

            {/* Executor */}
            <div className="flex flex-col items-center gap-1">
              <div className="px-4 py-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-400 text-sm font-medium min-w-[100px] text-center">
                Executor
                {executor && (
                  <span className="block text-xs text-green-600 mt-0.5">
                    {executor.active_count} active
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-600">LLM call</span>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-600 shrink-0" />

            {/* Store */}
            <div className="flex flex-col items-center gap-1">
              <div className="px-4 py-3 rounded-lg bg-idm-primary/10 border border-idm-primary/30 text-idm-primary text-sm font-medium min-w-[100px] text-center">
                Store
                {executor && (
                  <span className="block text-xs text-idm-primary/60 mt-0.5">
                    {executor.completed_today} today
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-600">Results + Events</span>
            </div>
          </div>
        </div>

        {/* Two Column Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Activity Log */}
          <div className="glass rounded-xl p-6 border border-idm-border">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-idm-primary" />
              Activity Log
            </h3>

            {activityLog.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">
                No completed or failed prompts yet.
              </p>
            ) : (
              <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
                {activityLog.map((prompt) => (
                  <div
                    key={prompt.prompt_id}
                    className="flex items-start gap-3 p-3 rounded-lg bg-idm-surface/50 border border-idm-border/50 hover:border-idm-border transition-colors"
                  >
                    {prompt.status === 'completed' ? (
                      <CheckCircle className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-300 truncate">
                        {prompt.content}
                      </p>
                      <div className="flex items-center gap-3 mt-1 text-xs text-gray-600">
                        <span>{prompt.provider_used ?? 'unknown'}</span>
                        {prompt.model_used && (
                          <>
                            <span className="text-gray-700">/</span>
                            <span>{prompt.model_used}</span>
                          </>
                        )}
                        {prompt.latency_ms != null && (
                          <span className="flex items-center gap-0.5">
                            <Clock className="w-3 h-3" />
                            {(prompt.latency_ms / 1000).toFixed(1)}s
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="text-xs text-gray-700 shrink-0">
                      {formatRelativeTime(prompt.completed_at ?? prompt.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right: Model Usage Stats */}
          <div className="glass rounded-xl p-6 border border-idm-border">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-yellow-400" />
              Model Usage
            </h3>

            {providerEntries.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">
                No usage data available yet.
              </p>
            ) : (
              <div className="space-y-3">
                {providerEntries.map(([provider, count]) => {
                  const maxCount = providerEntries[0]?.[1] ?? 1
                  const pct = Math.round((count / maxCount) * 100)
                  return (
                    <div key={provider}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm text-gray-300 font-medium">
                          {provider}
                        </span>
                        <span className="text-sm text-gray-500">{count}</span>
                      </div>
                      <div className="h-2 rounded-full bg-idm-surface overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-yellow-500 to-yellow-400 transition-all duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            {/* Summary Cards */}
            {executor && (
              <div className="grid grid-cols-2 gap-3 mt-6">
                <div className="p-3 rounded-lg bg-green-500/5 border border-green-500/20 text-center">
                  <div className="text-2xl font-bold text-green-400">
                    {executor.completed_today}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">Completed Today</div>
                </div>
                <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 text-center">
                  <div className="text-2xl font-bold text-red-400">
                    {executor.failed_today}
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">Failed Today</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

/** Format a timestamp into a relative time string */
function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diff = now - then
  const seconds = Math.floor(diff / 1000)

  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
