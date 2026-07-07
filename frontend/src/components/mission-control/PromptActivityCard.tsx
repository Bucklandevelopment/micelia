'use client'

import { Inbox, Cpu, XCircle, Clock, ListChecks } from 'lucide-react'

interface ActivityData {
  captured_today: number
  processed_today: number
  failed_today: number
  pending: number
  queued: number
}

const stats = [
  { key: 'captured_today', label: 'Captured', icon: Inbox, color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/30' },
  { key: 'pending', label: 'Pending', icon: Clock, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30' },
  { key: 'queued', label: 'Queued', icon: ListChecks, color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/30' },
  { key: 'processed_today', label: 'Processed', icon: Cpu, color: 'text-green-400', bg: 'bg-green-500/10 border-green-500/30' },
  { key: 'failed_today', label: 'Failed', icon: XCircle, color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/30' },
] as const

export function PromptActivityCard({ data }: { data?: ActivityData }) {
  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      <h3 className="text-sm font-medium text-gray-400 mb-3">Prompt Activity</h3>
      <div className="grid grid-cols-5 gap-2">
        {stats.map(({ key, label, icon: Icon, color, bg }) => (
          <div key={key} className={`flex flex-col items-center p-3 rounded-lg border ${bg}`}>
            <Icon className={`w-4 h-4 ${color} mb-1`} />
            <span className={`text-xl font-bold ${color}`}>
              {data ? data[key] : 0}
            </span>
            <span className="text-[10px] text-gray-500 mt-0.5">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function PromptActivitySkeleton() {
  return (
    <div className="glass rounded-xl p-5 border border-idm-border animate-pulse">
      <div className="h-4 w-28 bg-idm-surface rounded mb-3" />
      <div className="grid grid-cols-5 gap-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-20 rounded-lg bg-idm-surface" />
        ))}
      </div>
    </div>
  )
}
