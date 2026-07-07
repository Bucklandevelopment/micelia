'use client'

import { Clock, Loader2, CheckCircle, Layers } from 'lucide-react'
import { clsx } from 'clsx'
import { usePromptStats } from '@/hooks/usePrompts'

interface MetricCardProps {
  label: string
  value: number | string
  icon: React.ReactNode
  colorClass: string
  bgClass: string
  borderClass: string
  animated?: boolean
}

function MetricCard({
  label,
  value,
  icon,
  colorClass,
  bgClass,
  borderClass,
  animated,
}: MetricCardProps) {
  return (
    <div
      className={clsx(
        'glass rounded-xl p-4 border transition-all duration-200',
        borderClass
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className={clsx('p-2 rounded-lg', bgClass, colorClass)}>{icon}</div>
        {animated && (
          <span className="relative flex h-2.5 w-2.5">
            <span className={clsx('animate-ping absolute inline-flex h-full w-full rounded-full opacity-75', bgClass)} />
            <span className={clsx('relative inline-flex rounded-full h-2.5 w-2.5', bgClass)} />
          </span>
        )}
      </div>
      <div className={clsx('text-2xl font-bold', colorClass)}>{value}</div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  )
}

export function PromptStats() {
  const { data, isLoading } = usePromptStats()

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {Array.from({ length: 4 }, (_, i) => (
          <div
            key={i}
            className="glass rounded-xl p-4 border border-idm-border animate-pulse"
          >
            <div className="flex items-center justify-between mb-2">
              <div className="w-9 h-9 rounded-lg bg-idm-border" />
            </div>
            <div className="h-7 w-12 rounded bg-idm-border mb-1" />
            <div className="h-3 w-20 rounded bg-idm-border" />
          </div>
        ))}
      </div>
    )
  }

  const pendingCount = (data?.by_status?.pending ?? 0) + (data?.by_status?.queued ?? 0)
  const processingCount = data?.by_status?.processing ?? 0
  const completedToday = data?.completed_today ?? 0
  const total = data?.total ?? 0

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <MetricCard
        label="Pending"
        value={pendingCount}
        icon={<Clock className="w-4 h-4" />}
        colorClass="text-energy-conserving"
        bgClass="bg-energy-conserving/15"
        borderClass="border-energy-conserving/20"
      />
      <MetricCard
        label="Processing"
        value={processingCount}
        icon={<Loader2 className="w-4 h-4" />}
        colorClass="text-blue-400"
        bgClass="bg-blue-500/15"
        borderClass="border-blue-500/20"
        animated={processingCount > 0}
      />
      <MetricCard
        label="Completed Today"
        value={completedToday}
        icon={<CheckCircle className="w-4 h-4" />}
        colorClass="text-energy-abundant"
        bgClass="bg-energy-abundant/15"
        borderClass="border-energy-abundant/20"
      />
      <MetricCard
        label="Total Prompts"
        value={total}
        icon={<Layers className="w-4 h-4" />}
        colorClass="text-gray-400"
        bgClass="bg-gray-500/15"
        borderClass="border-idm-border"
      />
    </div>
  )
}
