'use client'

import { useMemo } from 'react'
import {
  Layers,
  Clock,
  Hash,
  CheckCircle,
  Edit3,
  ListPlus,
  Archive,
  Loader2,
  ArrowRight,
  Workflow,
  Shield,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useStaging, useApprovePrompt, useArchivePrompt, useUpdatePrompt } from '@/hooks/usePrompts'
import { usePromptUIStore } from '@/stores/promptStore'
import type { Prompt } from '@/types/api'

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

function SkeletonCard() {
  return (
    <div className="glass rounded-xl p-4 border border-idm-border animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="flex gap-2">
          <div className="h-4 w-16 rounded-full bg-idm-border" />
          <div className="h-4 w-12 rounded bg-idm-border" />
        </div>
        <div className="h-3 w-14 rounded bg-idm-border" />
      </div>
      <div className="space-y-2 mb-3">
        <div className="h-3 w-full rounded bg-idm-border" />
        <div className="h-3 w-2/3 rounded bg-idm-border" />
      </div>
      <div className="flex gap-2">
        <div className="h-7 w-20 rounded-lg bg-idm-border" />
        <div className="h-7 w-16 rounded-lg bg-idm-border" />
      </div>
    </div>
  )
}

interface StagingItemProps {
  prompt: Prompt
}

function StagingItem({ prompt }: StagingItemProps) {
  const { setSelectedPrompt } = usePromptUIStore()
  const approve = useApprovePrompt()
  const archive = useArchivePrompt()
  const update = useUpdatePrompt()

  const contentPreview =
    prompt.content.length > 140
      ? prompt.content.slice(0, 140) + '...'
      : prompt.content

  const isActing = approve.isPending || archive.isPending || update.isPending

  const statusBadge = prompt.status === 'classified'
    ? { label: 'Classified', classes: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30' }
    : { label: 'Staged', classes: 'bg-blue-500/15 text-blue-400 border-blue-500/30' }

  const suggestedWorkflow = (prompt.metadata?.suggested_workflow as string) || null
  const suggestedPolicy = (prompt.metadata?.suggested_policy as string) || null

  return (
    <div
      className={clsx(
        'glass rounded-xl p-4 border border-idm-border',
        'hover:border-idm-primary/30 hover:bg-idm-surface/80',
        'transition-all duration-200 group'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border',
              statusBadge.classes
            )}
          >
            <span className={clsx('w-1.5 h-1.5 rounded-full', prompt.status === 'classified' ? 'bg-indigo-400' : 'bg-blue-400')} />
            {statusBadge.label}
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

      {/* Content */}
      <button
        type="button"
        onClick={() => setSelectedPrompt(prompt.prompt_id)}
        className="w-full text-left"
      >
        <p className="text-sm text-gray-300 mb-3 leading-relaxed">{contentPreview}</p>
      </button>

      {/* Suggested workflow / policy */}
      {(suggestedWorkflow || suggestedPolicy) && (
        <div className="flex flex-wrap gap-2 mb-3">
          {suggestedWorkflow && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium bg-idm-primary/10 text-idm-primary border border-idm-primary/20">
              <Workflow className="w-3 h-3" />
              {suggestedWorkflow}
            </span>
          )}
          {suggestedPolicy && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
              <Shield className="w-3 h-3" />
              {suggestedPolicy}
            </span>
          )}
        </div>
      )}

      {/* Tags */}
      {prompt.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
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
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => approve.mutate(prompt.prompt_id)}
          disabled={isActing}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-energy-abundant/15 text-energy-abundant border border-energy-abundant/25 hover:bg-energy-abundant/25',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {approve.isPending ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <ArrowRight className="w-3 h-3" />
          )}
          Approve
        </button>

        <button
          type="button"
          onClick={() => setSelectedPrompt(prompt.prompt_id)}
          disabled={isActing}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-idm-surface text-gray-400 border border-idm-border hover:text-white hover:bg-idm-surface/80',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Edit3 className="w-3 h-3" />
          Edit
        </button>

        <button
          type="button"
          onClick={() => setSelectedPrompt(prompt.prompt_id)}
          disabled={isActing}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-idm-primary/10 text-idm-primary border border-idm-primary/20 hover:bg-idm-primary/20',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <ListPlus className="w-3 h-3" />
          To List
        </button>

        <div className="flex-1" />

        <button
          type="button"
          onClick={() => archive.mutate(prompt.prompt_id)}
          disabled={isActing}
          className="p-1.5 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-idm-surface transition-colors disabled:opacity-50"
          title="Archive"
        >
          <Archive className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

export function StagingPanel() {
  const { data, isLoading } = useStaging()

  const sortedPrompts = useMemo(() => {
    if (!data?.prompts) return []
    return [...data.prompts].sort((a, b) => {
      if (b.priority !== a.priority) return b.priority - a.priority
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
  }, [data?.prompts])

  if (isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (sortedPrompts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <Layers className="w-12 h-12 mb-3 text-gray-600" />
        <p className="text-sm font-medium">No prompts in staging</p>
        <p className="text-xs mt-1">Classify prompts from the Inbox to move them here</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-340px)]">
      {sortedPrompts.map((prompt) => (
        <StagingItem key={prompt.prompt_id} prompt={prompt} />
      ))}
    </div>
  )
}
