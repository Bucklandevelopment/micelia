'use client'

import { useMemo } from 'react'
import {
  Inbox,
  Clock,
  Hash,
  Zap,
  Tag,
  Archive,
  Trash2,
  Loader2,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useInbox, useClassifyPrompt, useArchivePrompt, useDeletePrompt } from '@/hooks/usePrompts'
import { usePromptUIStore } from '@/stores/promptStore'
import { promptsApi } from '@/lib/api'
import type { Prompt } from '@/types/api'
import { useMutation, useQueryClient } from '@tanstack/react-query'

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
        <div className="h-4 w-24 rounded bg-idm-border" />
        <div className="h-3 w-14 rounded bg-idm-border" />
      </div>
      <div className="space-y-2 mb-3">
        <div className="h-3 w-full rounded bg-idm-border" />
        <div className="h-3 w-3/4 rounded bg-idm-border" />
      </div>
      <div className="flex gap-2">
        <div className="h-7 w-16 rounded-lg bg-idm-border" />
        <div className="h-7 w-20 rounded-lg bg-idm-border" />
      </div>
    </div>
  )
}

interface InboxItemProps {
  prompt: Prompt
}

function InboxItem({ prompt }: InboxItemProps) {
  const { setSelectedPrompt } = usePromptUIStore()
  const classify = useClassifyPrompt()
  const archive = useArchivePrompt()
  const deletePrompt = useDeletePrompt()
  const queryClient = useQueryClient()

  const executeNow = useMutation({
    mutationFn: (id: string) => promptsApi.approvePrompt(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })

  const contentPreview =
    prompt.content.length > 140
      ? prompt.content.slice(0, 140) + '...'
      : prompt.content

  const isActing = classify.isPending || archive.isPending || deletePrompt.isPending || executeNow.isPending

  return (
    <div
      className={clsx(
        'glass rounded-xl p-4 border border-idm-border',
        'hover:border-idm-primary/30 hover:bg-idm-surface/80',
        'transition-all duration-200 group'
      )}
    >
      {/* Header: timestamp + source */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-gray-500/15 text-gray-400 border border-gray-500/30">
            <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
            Captured
          </span>
          {prompt.source && (
            <span className="text-[10px] text-gray-500">{prompt.source}</span>
          )}
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

      {/* Tags (auto-detected) */}
      {prompt.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {prompt.tags.slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-idm-primary/10 text-idm-primary/70"
            >
              <Hash className="w-2.5 h-2.5" />
              {tag}
            </span>
          ))}
          {prompt.tags.length > 5 && (
            <span className="text-[10px] text-gray-500">+{prompt.tags.length - 5}</span>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => classify.mutate({ id: prompt.prompt_id, data: {} })}
          disabled={isActing}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-blue-500/15 text-blue-400 border border-blue-500/25 hover:bg-blue-500/25',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {classify.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Tag className="w-3 h-3" />}
          Classify
        </button>

        <button
          type="button"
          onClick={() => executeNow.mutate(prompt.prompt_id)}
          disabled={isActing}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-energy-abundant/15 text-energy-abundant border border-energy-abundant/25 hover:bg-energy-abundant/25',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {executeNow.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
          Execute Now
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

        <button
          type="button"
          onClick={() => deletePrompt.mutate(prompt.prompt_id)}
          disabled={isActing}
          className="p-1.5 rounded-lg text-gray-500 hover:text-energy-critical hover:bg-energy-critical/10 transition-colors disabled:opacity-50"
          title="Delete"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

export function InboxPanel() {
  const { data, isLoading } = useInbox()

  const sortedPrompts = useMemo(() => {
    if (!data?.prompts) return []
    return [...data.prompts].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
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
        <Inbox className="w-12 h-12 mb-3 text-gray-600" />
        <p className="text-sm font-medium">Inbox is empty</p>
        <p className="text-xs mt-1">Write a quick note below to capture a new prompt</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-340px)]">
      {sortedPrompts.map((prompt) => (
        <InboxItem key={prompt.prompt_id} prompt={prompt} />
      ))}
    </div>
  )
}
