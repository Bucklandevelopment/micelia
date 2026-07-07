'use client'

import {
  Briefcase,
  Calendar,
  FileText,
  FolderKanban,
  Lightbulb,
  ListTodo,
  User,
  Layers,
} from 'lucide-react'
import { clsx } from 'clsx'
import { usePromptStats } from '@/hooks/usePrompts'
import { usePromptUIStore } from '@/stores/promptStore'
import type { ReactNode } from 'react'

const categoryIcons: Record<string, ReactNode> = {
  plan: <Lightbulb className="w-4 h-4" />,
  'short-term': <Calendar className="w-4 h-4" />,
  work: <Briefcase className="w-4 h-4" />,
  personal: <User className="w-4 h-4" />,
  routine: <ListTodo className="w-4 h-4" />,
  note: <FileText className="w-4 h-4" />,
  project: <FolderKanban className="w-4 h-4" />,
}

function getCategoryIcon(category: string): ReactNode {
  return categoryIcons[category] || <Layers className="w-4 h-4" />
}

export function CategorySidebar() {
  const { data, isLoading } = usePromptStats()
  const { filterCategory, setFilterCategory } = usePromptUIStore()

  const categories = data?.by_category ?? {}
  const totalCount = data?.total ?? 0
  const categoryEntries = Object.entries(categories).sort(([, a], [, b]) => b - a)

  return (
    <div className="glass rounded-xl p-4 border border-idm-border">
      <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-3 px-1">
        Categories
      </h2>

      <div className="space-y-0.5">
        {/* All categories option */}
        <button
          type="button"
          onClick={() => setFilterCategory(null)}
          className={clsx(
            'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors',
            filterCategory === null
              ? 'bg-idm-primary/10 text-idm-primary border border-idm-primary/20'
              : 'text-gray-400 hover:bg-idm-surface hover:text-gray-300'
          )}
        >
          <div className="flex items-center gap-2.5">
            <Layers className="w-4 h-4" />
            <span>All</span>
          </div>
          <span
            className={clsx(
              'text-xs font-medium px-1.5 py-0.5 rounded-full min-w-[24px] text-center',
              filterCategory === null
                ? 'bg-idm-primary/20 text-idm-primary'
                : 'bg-idm-border text-gray-500'
            )}
          >
            {totalCount}
          </span>
        </button>

        {/* Individual categories */}
        {isLoading ? (
          <div className="space-y-1 pt-1">
            {Array.from({ length: 5 }, (_, i) => (
              <div
                key={i}
                className="flex items-center justify-between px-3 py-2 animate-pulse"
              >
                <div className="flex items-center gap-2.5">
                  <div className="w-4 h-4 rounded bg-idm-border" />
                  <div className="h-3 w-16 rounded bg-idm-border" />
                </div>
                <div className="h-4 w-6 rounded-full bg-idm-border" />
              </div>
            ))}
          </div>
        ) : (
          categoryEntries.map(([category, count]) => (
            <button
              key={category}
              type="button"
              onClick={() =>
                setFilterCategory(filterCategory === category ? null : category)
              }
              className={clsx(
                'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors',
                filterCategory === category
                  ? 'bg-idm-primary/10 text-idm-primary border border-idm-primary/20'
                  : 'text-gray-400 hover:bg-idm-surface hover:text-gray-300'
              )}
            >
              <div className="flex items-center gap-2.5">
                {getCategoryIcon(category)}
                <span className="capitalize">{category}</span>
              </div>
              <span
                className={clsx(
                  'text-xs font-medium px-1.5 py-0.5 rounded-full min-w-[24px] text-center',
                  filterCategory === category
                    ? 'bg-idm-primary/20 text-idm-primary'
                    : 'bg-idm-border text-gray-500'
                )}
              >
                {count}
              </span>
            </button>
          ))
        )}
      </div>
    </div>
  )
}
