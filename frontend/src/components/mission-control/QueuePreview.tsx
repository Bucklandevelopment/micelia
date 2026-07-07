'use client'

import { ListOrdered, ArrowRight } from 'lucide-react'
import Link from 'next/link'

interface QueueItem {
  prompt_id: string
  content: string
  category: string
  priority: number
  created_at: string
}

const categoryColors: Record<string, string> = {
  work: 'text-blue-400 bg-blue-500/10',
  plan: 'text-purple-400 bg-purple-500/10',
  project: 'text-cyan-400 bg-cyan-500/10',
  routine: 'text-green-400 bg-green-500/10',
  personal: 'text-pink-400 bg-pink-500/10',
  note: 'text-gray-400 bg-gray-500/10',
  health: 'text-red-400 bg-red-500/10',
  learning: 'text-yellow-400 bg-yellow-500/10',
}

export function QueuePreview({ items }: { items?: QueueItem[] }) {
  const queue = items ?? []

  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-400 flex items-center gap-1.5">
          <ListOrdered className="w-4 h-4 text-purple-400" />
          Queue
        </h3>
        <Link href="/prompts" className="text-[10px] text-idm-primary hover:underline flex items-center gap-0.5">
          View all <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {queue.length === 0 ? (
        <p className="text-xs text-gray-600 text-center py-6">Queue empty</p>
      ) : (
        <div className="space-y-2">
          {queue.map((item) => (
            <div
              key={item.prompt_id}
              className="flex items-center gap-2 p-2.5 rounded-lg bg-idm-surface/50 border border-idm-border/50"
            >
              <span className="text-xs font-mono text-yellow-400 w-5 text-center shrink-0">
                {item.priority}
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded ${categoryColors[item.category] ?? categoryColors.note}`}>
                {item.category}
              </span>
              <span className="text-xs text-gray-300 truncate flex-1">{item.content}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function QueueSkeleton() {
  return (
    <div className="glass rounded-xl p-5 border border-idm-border animate-pulse">
      <div className="h-4 w-16 bg-idm-surface rounded mb-3" />
      <div className="space-y-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-10 rounded-lg bg-idm-surface" />
        ))}
      </div>
    </div>
  )
}
