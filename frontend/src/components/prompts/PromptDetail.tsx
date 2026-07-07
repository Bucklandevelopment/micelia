'use client'

import { useState } from 'react'
import {
  X,
  RotateCcw,
  Trash2,
  Clock,
  Cpu,
  DollarSign,
  Zap,
  Hash,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Star,
} from 'lucide-react'
import { clsx } from 'clsx'
import { usePrompt, useRetryPrompt, useDeletePrompt } from '@/hooks/usePrompts'
import { usePromptUIStore } from '@/stores/promptStore'

function formatDate(dateString: string | null): string {
  if (!dateString) return '--'
  return new Date(dateString).toLocaleString()
}

function formatTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return String(n)
}

function formatCost(cost: number | null): string {
  if (cost === null || cost === 0) return '--'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(2)}`
}

function formatLatency(ms: number | null): string {
  if (ms === null) return '--'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms}ms`
}

export function PromptDetail() {
  const { selectedPromptId, setSelectedPrompt, setShowDetail } = usePromptUIStore()
  const { data: prompt, isLoading } = usePrompt(selectedPromptId || '')
  const retryMutation = useRetryPrompt()
  const deleteMutation = useDeletePrompt()
  const [confirmDelete, setConfirmDelete] = useState(false)

  const handleClose = () => {
    setSelectedPrompt(null)
    setShowDetail(false)
    setConfirmDelete(false)
  }

  const handleRetry = () => {
    if (prompt) {
      retryMutation.mutate(prompt.prompt_id)
    }
  }

  const handleDelete = () => {
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    if (prompt) {
      deleteMutation.mutate(prompt.prompt_id, {
        onSuccess: handleClose,
      })
    }
  }

  if (!selectedPromptId) return null

  return (
    <div className="fixed inset-y-0 right-0 z-40 w-full max-w-lg">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* Panel */}
      <div className="relative h-full ml-auto w-full max-w-lg glass border-l border-idm-border overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 glass border-b border-idm-border px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Prompt Detail</h2>
          <button
            type="button"
            onClick={handleClose}
            className="p-2 rounded-lg hover:bg-idm-surface text-gray-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 text-idm-primary animate-spin" />
          </div>
        ) : prompt ? (
          <div className="p-6 space-y-6">
            {/* Status + Category */}
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={clsx(
                  'px-2.5 py-1 rounded-full text-xs font-medium border',
                  prompt.status === 'completed' && 'bg-energy-abundant/15 text-energy-abundant border-energy-abundant/30',
                  prompt.status === 'failed' && 'bg-energy-critical/15 text-energy-critical border-energy-critical/30',
                  prompt.status === 'processing' && 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30 animate-pulse',
                  prompt.status === 'queued' && 'bg-blue-500/15 text-blue-400 border-blue-500/30',
                  prompt.status === 'pending' && 'bg-gray-500/15 text-gray-400 border-gray-500/30',
                  prompt.status === 'reviewed' && 'bg-idm-primary/15 text-idm-primary border-idm-primary/30',
                  prompt.status === 'draft' && 'bg-gray-500/15 text-gray-400 border-gray-500/30'
                )}
              >
                {prompt.status}
              </span>
              <span className="px-2 py-1 rounded text-xs bg-idm-surface text-gray-400 border border-idm-border">
                {prompt.category}
              </span>
              <span className="text-xs text-gray-500">Priority: {prompt.priority}/10</span>
            </div>

            {/* Full content */}
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Content
              </h3>
              <div className="bg-idm-surface rounded-lg p-4 border border-idm-border">
                <p className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
                  {prompt.content}
                </p>
              </div>
            </div>

            {/* Output (if completed) */}
            {prompt.output && (
              <div>
                <h3 className="text-xs font-medium text-energy-abundant uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <CheckCircle className="w-3.5 h-3.5" />
                  Output
                </h3>
                <div className="bg-energy-abundant/5 rounded-lg p-4 border border-energy-abundant/20">
                  <p className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
                    {prompt.output}
                  </p>
                </div>
              </div>
            )}

            {/* Error (if failed) */}
            {prompt.error && (
              <div>
                <h3 className="text-xs font-medium text-energy-critical uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Error
                </h3>
                <div className="bg-energy-critical/5 rounded-lg p-4 border border-energy-critical/20">
                  <p className="text-sm text-energy-critical/80 whitespace-pre-wrap font-mono">
                    {prompt.error}
                  </p>
                </div>
              </div>
            )}

            {/* Review score */}
            {prompt.review_score !== null && (
              <div>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <Star className="w-3.5 h-3.5" />
                  Review Score
                </h3>
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-2 bg-idm-border rounded-full overflow-hidden">
                    <div
                      className={clsx(
                        'h-full rounded-full transition-all duration-500',
                        prompt.review_score >= 8
                          ? 'bg-energy-abundant'
                          : prompt.review_score >= 5
                            ? 'bg-energy-conserving'
                            : 'bg-energy-critical'
                      )}
                      style={{ width: `${(prompt.review_score / 10) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium text-white">
                    {prompt.review_score}/10
                  </span>
                </div>
              </div>
            )}

            {/* Metadata grid */}
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Details
              </h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
                  <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                    <Cpu className="w-3.5 h-3.5" />
                    <span className="text-[10px] uppercase tracking-wider">Model</span>
                  </div>
                  <p className="text-xs text-gray-300 truncate">
                    {prompt.model_used || '--'}
                  </p>
                </div>
                <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
                  <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                    <Zap className="w-3.5 h-3.5" />
                    <span className="text-[10px] uppercase tracking-wider">Provider</span>
                  </div>
                  <p className="text-xs text-gray-300 truncate">
                    {prompt.provider_used || '--'}
                  </p>
                </div>
                <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
                  <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                    <Hash className="w-3.5 h-3.5" />
                    <span className="text-[10px] uppercase tracking-wider">Tokens In</span>
                  </div>
                  <p className="text-xs text-gray-300">
                    {formatTokens(prompt.tokens_input)}
                  </p>
                </div>
                <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
                  <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                    <Hash className="w-3.5 h-3.5" />
                    <span className="text-[10px] uppercase tracking-wider">Tokens Out</span>
                  </div>
                  <p className="text-xs text-gray-300">
                    {formatTokens(prompt.tokens_output)}
                  </p>
                </div>
                <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
                  <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span className="text-[10px] uppercase tracking-wider">Latency</span>
                  </div>
                  <p className="text-xs text-gray-300">
                    {formatLatency(prompt.latency_ms)}
                  </p>
                </div>
                <div className="bg-idm-surface rounded-lg p-3 border border-idm-border">
                  <div className="flex items-center gap-1.5 text-gray-500 mb-1">
                    <DollarSign className="w-3.5 h-3.5" />
                    <span className="text-[10px] uppercase tracking-wider">Cost</span>
                  </div>
                  <p className="text-xs text-gray-300">
                    {formatCost(prompt.cost_usd)}
                  </p>
                </div>
              </div>
            </div>

            {/* Tags */}
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Tags
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {prompt.tags.length > 0 ? (
                  prompt.tags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-idm-primary/10 text-idm-primary border border-idm-primary/20"
                    >
                      <Hash className="w-3 h-3" />
                      {tag}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-gray-600">No tags</span>
                )}
              </div>
            </div>

            {/* Timestamps */}
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
                Timeline
              </h3>
              <div className="space-y-1 text-xs text-gray-400">
                <div className="flex justify-between">
                  <span>Created</span>
                  <span>{formatDate(prompt.created_at)}</span>
                </div>
                {prompt.processing_at && (
                  <div className="flex justify-between">
                    <span>Processing</span>
                    <span>{formatDate(prompt.processing_at)}</span>
                  </div>
                )}
                {prompt.completed_at && (
                  <div className="flex justify-between">
                    <span>Completed</span>
                    <span>{formatDate(prompt.completed_at)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3 pt-4 border-t border-idm-border">
              {prompt.status === 'failed' && (
                <button
                  type="button"
                  onClick={handleRetry}
                  disabled={retryMutation.isPending}
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    'bg-energy-conserving/15 text-energy-conserving border border-energy-conserving/30',
                    'hover:bg-energy-conserving/25',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  {retryMutation.isPending ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RotateCcw className="w-4 h-4" />
                  )}
                  Retry
                </button>
              )}
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                  confirmDelete
                    ? 'bg-energy-critical/25 text-energy-critical border border-energy-critical/50'
                    : 'bg-energy-critical/10 text-energy-critical/70 border border-energy-critical/20',
                  'hover:bg-energy-critical/30',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
                {confirmDelete ? 'Confirm Delete' : 'Delete'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center py-20 text-gray-500">
            <p className="text-sm">Prompt not found</p>
          </div>
        )}
      </div>
    </div>
  )
}
