'use client'

import { useMemo } from 'react'
import { Loader2, Inbox } from 'lucide-react'
import { usePrompts } from '@/hooks/usePrompts'
import { usePromptUIStore } from '@/stores/promptStore'
import { PromptCard } from './PromptCard'
import type { Prompt } from '@/types/api'

function SkeletonCard() {
  return (
    <div className="glass rounded-xl p-4 border border-idm-border animate-pulse">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className="h-4 w-16 rounded-full bg-idm-border" />
          <div className="h-4 w-12 rounded bg-idm-border" />
        </div>
        <div className="h-3 w-14 rounded bg-idm-border" />
      </div>
      <div className="space-y-2 mb-3">
        <div className="h-3 w-full rounded bg-idm-border" />
        <div className="h-3 w-3/4 rounded bg-idm-border" />
      </div>
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          <div className="h-4 w-10 rounded bg-idm-border" />
          <div className="h-4 w-10 rounded bg-idm-border" />
        </div>
        <div className="flex gap-0.5">
          {Array.from({ length: 10 }, (_, i) => (
            <div key={i} className="w-1 h-3 rounded-full bg-idm-border" />
          ))}
        </div>
      </div>
    </div>
  )
}

export function PromptQueue() {
  const { filterStatus, filterCategory, selectedPromptId, setSelectedPrompt } =
    usePromptUIStore()

  const { data, isLoading } = usePrompts({
    status: filterStatus || undefined,
    category: filterCategory || undefined,
    limit: 50,
  })

  const sortedPrompts = useMemo(() => {
    if (!data?.prompts) return []
    return [...data.prompts].sort((a: Prompt, b: Prompt) => {
      // Sort by priority desc, then created_at desc
      if (b.priority !== a.priority) return b.priority - a.priority
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })
  }, [data?.prompts])

  if (isLoading) {
    return (
      <div className="space-y-3 p-1">
        {Array.from({ length: 5 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    )
  }

  if (sortedPrompts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <Inbox className="w-12 h-12 mb-3 text-gray-600" />
        <p className="text-sm font-medium">No prompts found</p>
        <p className="text-xs mt-1">
          {filterStatus || filterCategory
            ? 'Try clearing your filters'
            : 'Write a quick note to get started'}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3 p-1 overflow-y-auto max-h-[calc(100vh-320px)]">
      {sortedPrompts.map((prompt: Prompt) => (
        <PromptCard
          key={prompt.prompt_id}
          prompt={prompt}
          isSelected={selectedPromptId === prompt.prompt_id}
          onClick={() => setSelectedPrompt(prompt.prompt_id)}
        />
      ))}
    </div>
  )
}
