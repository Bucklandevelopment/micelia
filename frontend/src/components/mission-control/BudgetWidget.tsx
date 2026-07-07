'use client'

import { DollarSign } from 'lucide-react'

interface BudgetData {
  daily_spent: number
  daily_limit: number
  monthly_spent: number
  monthly_limit: number
}

function ProgressBar({ label, spent, limit }: { label: string; spent: number; limit: number }) {
  const pct = limit > 0 ? Math.min(100, (spent / limit) * 100) : 0
  const color =
    pct > 90 ? 'from-red-500 to-red-400' :
    pct > 70 ? 'from-yellow-500 to-yellow-400' :
    'from-green-500 to-green-400'

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-400">{label}</span>
        <span className="text-xs text-gray-500">
          ${spent.toFixed(2)} / ${limit > 0 ? `$${limit.toFixed(2)}` : 'unlimited'}
        </span>
      </div>
      <div className="h-2 rounded-full bg-idm-surface overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export function BudgetWidget({ data }: { data?: BudgetData }) {
  const d = data ?? { daily_spent: 0, daily_limit: 0, monthly_spent: 0, monthly_limit: 0 }

  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-1.5">
        <DollarSign className="w-4 h-4 text-yellow-400" />
        Budget
      </h3>
      <div className="space-y-3">
        <ProgressBar label="Daily" spent={d.daily_spent} limit={d.daily_limit} />
        <ProgressBar label="Monthly" spent={d.monthly_spent} limit={d.monthly_limit} />
      </div>
      {d.daily_limit === 0 && d.monthly_limit === 0 && (
        <p className="text-[10px] text-gray-600 mt-2">No budget limits configured</p>
      )}
    </div>
  )
}

export function BudgetSkeleton() {
  return (
    <div className="glass rounded-xl p-5 border border-idm-border animate-pulse">
      <div className="h-4 w-20 bg-idm-surface rounded mb-3" />
      <div className="space-y-4">
        <div className="h-2 bg-idm-surface rounded-full" />
        <div className="h-2 bg-idm-surface rounded-full" />
      </div>
    </div>
  )
}
