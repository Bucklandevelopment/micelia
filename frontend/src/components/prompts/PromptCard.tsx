'use client'

import { Clock, Hash, Tag } from 'lucide-react'
import { clsx } from 'clsx'
import type { Prompt, PromptStatus } from '@/types/api'

interface PromptCardProps {
  prompt: Prompt
  onClick: () => void
  isSelected: boolean
}

const statusConfig: Record<PromptStatus, { label: string; classes: string }> = {
  captured: {
    label: 'Captured',
    classes: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  },
  classified: {
    label: 'Classified',
    classes: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
  },
  staged: {
    label: 'Staged',
    classes: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  },
  pending: {
    label: 'Pending',
    classes: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  },
  draft: {
    label: 'Draft',
    classes: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  },
  queued: {
    label: 'Queued',
    classes: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  },
  processing: {
    label: 'Processing',
    classes: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30 animate-pulse',
  },
  completed: {
    label: 'Completed',
    classes: 'bg-energy-abundant/15 text-energy-abundant border-energy-abundant/30',
  },
  failed: {
    label: 'Failed',
    classes: 'bg-energy-critical/15 text-energy-critical border-energy-critical/30',
  },
  reviewed: {
    label: 'Reviewed',
    classes: 'bg-idm-primary/15 text-idm-primary border-idm-primary/30',
  },
  archived: {
    label: 'Archived',
    classes: 'bg-gray-600/15 text-gray-500 border-gray-600/30',
  },
}

function formatRelativeTime(dateString: string): string {
  const now = Date.now()
  const then = new Date(dateString).getTime()
  const diffMs = now - then

  const seconds = Math.floor(diffMs / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

function PriorityBar({ priority }: { priority: number }) {
  return (
    <div className="flex items-center gap-0.5" title={`Priority ${priority}/10`}>
      {Array.from({ length: 10 }, (_, i) => (
        <div
          key={i}
          className={clsx(
            'w-1 h-3 rounded-full transition-colors',
            i < priority
              ? priority >= 8
                ? 'bg-energy-critical'
                : priority >= 5
                  ? 'bg-energy-conserving'
                  : 'bg-idm-primary'
              : 'bg-idm-border'
          )}
        />
      ))}
    </div>
  )
}

export function PromptCard({ prompt, onClick, isSelected }: PromptCardProps) {
  const status = statusConfig[prompt.status] || statusConfig.pending
  const contentPreview =
    prompt.content.length > 120
      ? prompt.content.slice(0, 120) + '...'
      : prompt.content

  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'w-full text-left glass rounded-xl p-4 border transition-all duration-200 group',
        isSelected
          ? 'border-idm-primary/50 bg-idm-primary/5 shadow-lg shadow-idm-primary/10'
          : 'border-idm-border hover:border-idm-primary/30 hover:bg-idm-surface/80'
      )}
    >
      {/* Top row: status + priority + time */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border',
              status.classes
            )}
          >
            {status.label}
          </span>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-idm-surface text-gray-400 border border-idm-border">
            {prompt.category}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="w-3 h-3" />
          {formatRelativeTime(prompt.created_at)}
        </div>
      </div>

      {/* Content preview */}
      <p className="text-sm text-gray-300 mb-3 leading-relaxed">{contentPreview}</p>

      {/* Bottom row: tags + priority */}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-1">
          {prompt.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-idm-primary/10 text-idm-primary/70"
            >
              <Hash className="w-2.5 h-2.5" />
              {tag}
            </span>
          ))}
          {prompt.tags.length > 4 && (
            <span className="text-[10px] text-gray-500">+{prompt.tags.length - 4}</span>
          )}
        </div>
        <PriorityBar priority={prompt.priority} />
      </div>
    </button>
  )
}
