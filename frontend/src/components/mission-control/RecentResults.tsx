'use client'

import { CheckCircle, Clock, ArrowRight } from 'lucide-react'
import Link from 'next/link'

interface ResultItem {
  prompt_id: string
  content: string
  provider_used: string
  model_used: string
  latency_ms: number | null
  cost_usd: number | null
  completed_at: string
}

function formatRelative(iso: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h`
  return `${Math.floor(h / 24)}d`
}

export function RecentResults({ items }: { items?: ResultItem[] }) {
  const results = items ?? []

  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-400 flex items-center gap-1.5">
          <CheckCircle className="w-4 h-4 text-green-400" />
          Recent Results
        </h3>
        <Link href="/monitor" className="text-[10px] text-idm-primary hover:underline flex items-center gap-0.5">
          View all <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {results.length === 0 ? (
        <p className="text-xs text-gray-600 text-center py-6">No results yet</p>
      ) : (
        <div className="space-y-2">
          {results.map((item) => (
            <div
              key={item.prompt_id}
              className="p-2.5 rounded-lg bg-idm-surface/50 border border-idm-border/50"
            >
              <p className="text-xs text-gray-300 truncate mb-1">{item.content}</p>
              <div className="flex items-center gap-2 text-[10px] text-gray-600">
                <span>{item.provider_used}</span>
                {item.model_used && (
                  <>
                    <span className="text-gray-700">/</span>
                    <span>{item.model_used}</span>
                  </>
                )}
                {item.latency_ms != null && (
                  <span className="flex items-center gap-0.5">
                    <Clock className="w-2.5 h-2.5" />
                    {(item.latency_ms / 1000).toFixed(1)}s
                  </span>
                )}
                {item.cost_usd != null && item.cost_usd > 0 && (
                  <span>${item.cost_usd.toFixed(4)}</span>
                )}
                <span className="ml-auto">{formatRelative(item.completed_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ResultsSkeleton() {
  return (
    <div className="glass rounded-xl p-5 border border-idm-border animate-pulse">
      <div className="h-4 w-28 bg-idm-surface rounded mb-3" />
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-14 rounded-lg bg-idm-surface" />
        ))}
      </div>
    </div>
  )
}
