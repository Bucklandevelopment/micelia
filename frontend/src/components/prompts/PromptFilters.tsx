'use client'

import { Filter, X } from 'lucide-react'
import { clsx } from 'clsx'
import { usePromptUIStore } from '@/stores/promptStore'
import type { PromptStatus, PromptCategory } from '@/types/api'

const STATUSES: { value: string | null; label: string }[] = [
  { value: null, label: 'All Statuses' },
  { value: 'pending', label: 'Pending' },
  { value: 'queued', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'draft', label: 'Draft' },
]

const CATEGORIES: { value: string | null; label: string }[] = [
  { value: null, label: 'All Categories' },
  { value: 'plan', label: 'Plan' },
  { value: 'short-term', label: 'Short-term' },
  { value: 'work', label: 'Work' },
  { value: 'personal', label: 'Personal' },
  { value: 'routine', label: 'Routine' },
  { value: 'note', label: 'Note' },
  { value: 'project', label: 'Project' },
]

export function PromptFilters() {
  const { filterStatus, filterCategory, setFilterStatus, setFilterCategory, clearFilters } =
    usePromptUIStore()

  const hasFilters = filterStatus !== null || filterCategory !== null

  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex items-center gap-1.5 text-gray-500">
        <Filter className="w-4 h-4" />
        <span className="text-xs font-medium uppercase tracking-wider">Filters</span>
      </div>

      {/* Status dropdown */}
      <select
        value={filterStatus || ''}
        onChange={(e) => setFilterStatus(e.target.value || null)}
        className={clsx(
          'bg-idm-surface border border-idm-border rounded-lg px-3 py-1.5',
          'text-sm text-gray-300 appearance-none cursor-pointer',
          'focus:outline-none focus:border-idm-primary/50 focus:ring-1 focus:ring-idm-primary/20',
          'transition-colors',
          filterStatus && 'border-idm-primary/40 text-idm-primary'
        )}
      >
        {STATUSES.map((s) => (
          <option key={s.value || 'all'} value={s.value || ''}>
            {s.label}
          </option>
        ))}
      </select>

      {/* Category dropdown */}
      <select
        value={filterCategory || ''}
        onChange={(e) => setFilterCategory(e.target.value || null)}
        className={clsx(
          'bg-idm-surface border border-idm-border rounded-lg px-3 py-1.5',
          'text-sm text-gray-300 appearance-none cursor-pointer',
          'focus:outline-none focus:border-idm-primary/50 focus:ring-1 focus:ring-idm-primary/20',
          'transition-colors',
          filterCategory && 'border-idm-primary/40 text-idm-primary'
        )}
      >
        {CATEGORIES.map((c) => (
          <option key={c.value || 'all'} value={c.value || ''}>
            {c.label}
          </option>
        ))}
      </select>

      {/* Clear filters */}
      {hasFilters && (
        <button
          type="button"
          onClick={clearFilters}
          className={clsx(
            'inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium',
            'bg-energy-critical/10 text-energy-critical/80 border border-energy-critical/20',
            'hover:bg-energy-critical/20 transition-colors'
          )}
        >
          <X className="w-3 h-3" />
          Clear
        </button>
      )}
    </div>
  )
}
