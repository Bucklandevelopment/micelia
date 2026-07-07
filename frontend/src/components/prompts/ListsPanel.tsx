'use client'

import { useState } from 'react'
import {
  FileText,
  Calendar,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  ChevronRight,
  List,
  Loader2,
  Plus,
} from 'lucide-react'
import { clsx } from 'clsx'
import { usePromptLists } from '@/hooks/usePrompts'
import type { PromptList } from '@/types/api'

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function countListItems(contentMd: string): number {
  if (!contentMd) return 0
  const lines = contentMd.split('\n').filter((l) => l.trim().match(/^[-*+]\s|^\d+\.\s/))
  return lines.length
}

function SkeletonCard() {
  return (
    <div className="glass rounded-xl p-4 border border-idm-border animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-idm-border" />
          <div>
            <div className="h-4 w-28 rounded bg-idm-border mb-1" />
            <div className="h-3 w-20 rounded bg-idm-border" />
          </div>
        </div>
        <div className="w-5 h-5 rounded bg-idm-border" />
      </div>
      <div className="h-3 w-16 rounded bg-idm-border mt-2" />
    </div>
  )
}

interface ListItemProps {
  list: PromptList
}

function ListItem({ list }: ListItemProps) {
  const [expanded, setExpanded] = useState(false)

  const itemCount = countListItems(list.content_md)
  const contentPreview =
    list.content_md.length > 120
      ? list.content_md.slice(0, 120) + '...'
      : list.content_md

  return (
    <div
      className={clsx(
        'glass rounded-xl p-4 border border-idm-border',
        'hover:border-idm-primary/30 hover:bg-idm-surface/80',
        'transition-all duration-200'
      )}
    >
      {/* Header */}
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

      {/* Category + item count */}
      <div className="flex items-center gap-2 mb-2">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-idm-surface text-gray-400 border border-idm-border">
          {list.category}
        </span>
        <span className="inline-flex items-center gap-1 text-[10px] text-gray-500">
          <List className="w-3 h-3" />
          {itemCount} items
        </span>
      </div>

      {/* Expandable content */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left flex items-start gap-1.5 mb-2"
      >
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-gray-500 mt-0.5 shrink-0" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-gray-500 mt-0.5 shrink-0" />
        )}
        <span className="text-xs text-gray-400">
          {expanded ? 'Hide content' : 'Show content'}
        </span>
      </button>

      {expanded && list.content_md && (
        <div className="bg-idm-surface/50 rounded-lg p-3 border border-idm-border/50 mb-3">
          <pre className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap font-mono">
            {list.content_md}
          </pre>
        </div>
      )}

      {!expanded && contentPreview && (
        <p className="text-xs text-gray-400 leading-relaxed mb-3 font-mono bg-idm-surface/50 rounded p-2 border border-idm-border/50 line-clamp-2">
          {contentPreview}
        </p>
      )}

      {/* Footer */}
      <div className="flex items-center gap-1.5 text-[10px] text-gray-600">
        <Calendar className="w-3 h-3" />
        <span>Created {formatDate(list.created_at)}</span>
        {list.updated_at && (
          <>
            <span className="text-gray-700">|</span>
            <span>Updated {formatDate(list.updated_at)}</span>
          </>
        )}
      </div>
    </div>
  )
}

export function ListsPanel() {
  const { data, isLoading } = usePromptLists()

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 3 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  const lists = data?.lists ?? []

  if (lists.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <FileText className="w-12 h-12 mb-3 text-gray-600" />
        <p className="text-sm font-medium">No prompt lists yet</p>
        <p className="text-xs mt-1">Create lists to organize recurring prompts and routines</p>
      </div>
    )
  }

  // Separate active vs inactive
  const activeLists = lists.filter((l) => l.is_active)
  const inactiveLists = lists.filter((l) => !l.is_active)

  return (
    <div className="space-y-4 overflow-y-auto max-h-[calc(100vh-340px)]">
      {/* Active lists */}
      {activeLists.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2 px-1">
            Active ({activeLists.length})
          </h3>
          <div className="space-y-3">
            {activeLists.map((list) => (
              <ListItem key={list.list_id} list={list} />
            ))}
          </div>
        </div>
      )}

      {/* Inactive lists */}
      {inactiveLists.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 px-1">
            Inactive ({inactiveLists.length})
          </h3>
          <div className="space-y-3">
            {inactiveLists.map((list) => (
              <ListItem key={list.list_id} list={list} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
