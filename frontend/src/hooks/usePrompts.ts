'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { promptsApi } from '@/lib/api'
import type { PromptListResponse, Prompt, PromptStats, PipelineStatus, PromptList } from '@/types/api'

interface UsePromptsOptions {
  status?: string
  category?: string
  source?: string
  limit?: number
  offset?: number
}

export function usePrompts(options: UsePromptsOptions = {}) {
  return useQuery<PromptListResponse>({
    queryKey: ['prompts', options],
    queryFn: () => promptsApi.list(options),
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

export function usePrompt(promptId: string) {
  return useQuery<Prompt>({
    queryKey: ['prompts', promptId],
    queryFn: () => promptsApi.get(promptId),
    enabled: !!promptId,
  })
}

export function usePromptStats() {
  return useQuery<PromptStats>({
    queryKey: ['prompts', 'stats'],
    queryFn: () => promptsApi.stats(),
    refetchInterval: 10000,
    staleTime: 5000,
  })
}

// ==================== PANEL QUERIES ====================

export function useInbox() {
  return useQuery<PromptListResponse>({
    queryKey: ['prompts', 'inbox'],
    queryFn: () => promptsApi.getInbox(),
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

export function useStaging() {
  return useQuery<PromptListResponse>({
    queryKey: ['prompts', 'staging'],
    queryFn: () => promptsApi.getStaging(),
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

export function useActiveQueue() {
  return useQuery<PromptListResponse>({
    queryKey: ['prompts', 'queue'],
    queryFn: () => promptsApi.list({ status: 'pending,queued,processing', limit: 50 }),
    refetchInterval: 3000,
    staleTime: 1000,
  })
}

export function useResults() {
  return useQuery<PromptListResponse>({
    queryKey: ['prompts', 'results'],
    queryFn: () => promptsApi.list({ status: 'completed,reviewed', limit: 50 }),
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

export function usePromptLists() {
  return useQuery<{ lists: PromptList[]; count: number }>({
    queryKey: ['prompts', 'lists'],
    queryFn: () => promptsApi.listLists(),
    staleTime: 30000,
  })
}

export function usePromptList(slug: string) {
  return useQuery<PromptList>({
    queryKey: ['prompts', 'lists', slug],
    queryFn: () => promptsApi.getList(slug),
    enabled: !!slug,
  })
}

export function usePipelineStatus() {
  return useQuery<PipelineStatus>({
    queryKey: ['prompts', 'pipeline'],
    queryFn: () => promptsApi.pipelineStatus(),
    refetchInterval: 5000,
    staleTime: 2000,
  })
}

// ==================== MUTATIONS ====================

export function useCreatePrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { content: string; category?: string; priority?: number; tags?: string[]; prefer_paid?: boolean }) =>
      promptsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useCreateNote() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ text, tags }: { text: string; tags?: string[] }) =>
      promptsApi.createNote(text, tags),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useUpdatePrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<Prompt> }) =>
      promptsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useDeletePrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => promptsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useRetryPrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => promptsApi.retry(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useClassifyPrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { category?: string; tags?: string[] } }) =>
      promptsApi.classifyPrompt(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useStagePrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => promptsApi.stagePrompt(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useApprovePrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => promptsApi.approvePrompt(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function useArchivePrompt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => promptsApi.archivePrompt(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function usePromoteToList() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, slug }: { id: string; slug: string }) =>
      promptsApi.promoteToList(id, slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function usePromoteToSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name: string; trigger_pattern: string } }) =>
      promptsApi.promoteToSkill(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] })
    },
  })
}

export function usePipelineControl() {
  const queryClient = useQueryClient()
  return {
    pause: useMutation({
      mutationFn: () => promptsApi.pipelinePause(),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts', 'pipeline'] }),
    }),
    resume: useMutation({
      mutationFn: () => promptsApi.pipelineResume(),
      onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts', 'pipeline'] }),
    }),
  }
}
