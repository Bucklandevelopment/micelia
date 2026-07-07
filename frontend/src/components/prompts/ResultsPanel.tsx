'use client'

import { useMemo, useState } from 'react'
import {
  CheckCircle,
  Clock,
  Hash,
  ChevronDown,
  ChevronRight,
  Archive,
  ListPlus,
  Sparkles,
  Cpu,
  DollarSign,
  Timer,
  Loader2,
  FileText,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useResults, useArchivePrompt, usePromoteToList, usePromoteToSkill } from '@/hooks/usePrompts'
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

function formatDuration(ms: number | null): string {
  if (!ms) return '--'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatCost(cost: number | null): string {
  if (!cost) return '--'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

function SkeletonCard() {
  return (
    <div className="glass rounded-xl p-4 border border-idm-border animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="h-4 w-20 rounded-full bg-idm-border" />
        <div className="h-3 w-14 rounded bg-idm-border" />
      </div>
      <div className="space-y-2 mb-3">
        <div className="h-3 w-full rounded bg-idm-border" />
        <div className="h-3 w-1/2 rounded bg-idm-border" />
      </div>
      <div className="h-16 w-full rounded bg-idm-border" />
    </div>
  )
}

interface ResultItemProps {
  prompt: Prompt
}

function ResultItem({ prompt }: ResultItemProps) {
  const [expanded, setExpanded] = useState(false)
  const { setSelectedPrompt } = usePromptUIStore()
  const archive = useArchivePrompt()

  const contentPreview =
    prompt.content.length > 100
      ? prompt.content.slice(0, 100) + '...'
      : prompt.content

  const outputPreview =
    prompt.output && prompt.output.length > 200
      ? prompt.output.slice(0, 200) + '...'
      : prompt.output

  const isCompleted = prompt.status === 'completed'
  const isReviewed = prompt.status === 'reviewed'

  return (
    <div
      className={clsx(
        'glass rounded-xl p-4 border border-idm-border',
        'hover:border-idm-primary/30',
        'transition-all duration-200'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium border',
              isReviewed
                ? 'bg-idm-primary/15 text-idm-primary border-idm-primary/30'
                : 'bg-energy-abundant/15 text-energy-abundant border-energy-abundant/30'
            )}
          >
            <CheckCircle className="w-3 h-3" />
            {isReviewed ? 'Reviewed' : 'Completed'}
          </span>
          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-idm-surface text-gray-400 border border-idm-border">
            {prompt.category}
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-500">
          <Clock className="w-3 h-3" />
          {formatRelativeTime(prompt.completed_at || prompt.created_at)}
        </div>
      </div>

      {/* Original prompt (collapsible) */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left flex items-start gap-2 mb-2"
      >
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-gray-500 mt-0.5 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-500 mt-0.5 shrink-0" />
        )}
        <p className="text-xs text-gray-400 leading-relaxed">
          {expanded ? prompt.content : contentPreview}
        </p>
      </button>

      {/* Output */}
      {prompt.output && (
        <div className="bg-idm-surface/50 rounded-lg p-3 border border-idm-border/50 mb-3">
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
            {expanded ? prompt.output : outputPreview}
          </p>
          {!expanded && prompt.output.length > 200 && (
            <button
              type="button"
              onClick={() => setExpanded(true)}
              className="text-xs text-idm-primary hover:text-idm-primary/80 mt-2 transition-colors"
            >
              Show full output
            </button>
          )}
        </div>
      )}

      {/* Metrics row */}
      <div className="flex items-center gap-4 mb-3 text-[10px] text-gray-500">
        {prompt.model_used && (
          <span className="inline-flex items-center gap-1">
            <Cpu className="w-3 h-3" />
            {prompt.model_used}
          </span>
        )}
        <span className="inline-flex items-center gap-1">
          <Timer className="w-3 h-3" />
          {formatDuration(prompt.latency_ms)}
        </span>
        <span className="inline-flex items-center gap-1">
          <DollarSign className="w-3 h-3" />
          {formatCost(prompt.cost_usd)}
        </span>
        {(prompt.tokens_input > 0 || prompt.tokens_output > 0) && (
          <span className="inline-flex items-center gap-1">
            <FileText className="w-3 h-3" />
            {prompt.tokens_input + prompt.tokens_output} tok
          </span>
        )}
      </div>

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
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => archive.mutate(prompt.prompt_id)}
          disabled={archive.isPending}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-idm-surface text-gray-400 border border-idm-border hover:text-white hover:bg-idm-surface/80',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          {archive.isPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Archive className="w-3 h-3" />}
          Archive
        </button>

        <button
          type="button"
          onClick={() => setSelectedPrompt(prompt.prompt_id)}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-idm-primary/10 text-idm-primary border border-idm-primary/20 hover:bg-idm-primary/20'
          )}
        >
          <ListPlus className="w-3 h-3" />
          To List
        </button>

        <button
          type="button"
          onClick={() => setSelectedPrompt(prompt.prompt_id)}
          className={clsx(
            'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
            'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 hover:bg-yellow-500/20'
          )}
        >
          <Sparkles className="w-3 h-3" />
          To Skill
        </button>
      </div>
    </div>
  )
}

export function ResultsPanel() {
  const { data, isLoading } = useResults()

  const sortedPrompts = useMemo(() => {
    if (!data?.prompts) return []
    return [...data.prompts].sort(
      (a, b) =>
        new Date(b.completed_at || b.created_at).getTime() -
        new Date(a.completed_at || a.created_at).getTime()
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
        <CheckCircle className="w-12 h-12 mb-3 text-gray-600" />
        <p className="text-sm font-medium">No completed prompts yet</p>
        <p className="text-xs mt-1">Prompts that finish processing will appear here</p>
      </div>
    )
  }

  return (
    <div className="space-y-3 overflow-y-auto max-h-[calc(100vh-340px)]">
      {sortedPrompts.map((prompt) => (
        <ResultItem key={prompt.prompt_id} prompt={prompt} />
      ))}
    </div>
  )
}
