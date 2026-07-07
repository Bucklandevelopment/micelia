'use client'

import { FileText, Calendar, ToggleLeft, ToggleRight } from 'lucide-react'
import { clsx } from 'clsx'
import type { PromptList } from '@/types/api'

interface PromptListCardProps {
  list: PromptList
  isSelected?: boolean
  onClick: () => void
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export function PromptListCard({ list, isSelected, onClick }: PromptListCardProps) {
  const contentPreview =
    list.content_md.length > 100
      ? list.content_md.slice(0, 100) + '...'
      : list.content_md

  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        'w-full text-left glass rounded-xl p-4 border border-idm-border',
        isSelected ? 'border-idm-primary/50 bg-idm-surface/80' : 'hover:border-idm-primary/30 hover:bg-idm-surface/80',
        'transition-all duration-200 group'
      )}
    >
      {/* Top row: name + toggle */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-idm-primary/10 shrink-0">
            <FileText className="w-4 h-4 text-idm-primary" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-white truncate">{list.name}</h3>
            {list.description && (
              <p className="text-xs text-gray-500 truncate">{list.description}</p>
            )}
          </div>
        </div>
        <div
          className={clsx(
            'shrink-0 ml-2',
            list.is_active ? 'text-energy-abundant' : 'text-gray-500'
          )}
          title={list.is_active ? 'Active' : 'Inactive'}
        >
          {list.is_active ? (
            <ToggleRight className="w-5 h-5" />
          ) : (
            <ToggleLeft className="w-5 h-5" />
          )}
        </div>
      </div>

      {/* Category chip */}
      <div className="mb-2">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-idm-surface text-gray-400 border border-idm-border">
          {list.category}
        </span>
      </div>

      {/* Content preview */}
      {contentPreview && (
        <p className="text-xs text-gray-400 leading-relaxed mb-3 font-mono bg-idm-surface/50 rounded p-2 border border-idm-border/50">
          {contentPreview}
        </p>
      )}

      {/* Footer: created date */}
      <div className="flex items-center gap-1.5 text-[10px] text-gray-600">
        <Calendar className="w-3 h-3" />
        <span>Created {formatDate(list.created_at)}</span>
      </div>
    </button>
  )
}
