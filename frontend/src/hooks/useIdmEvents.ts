'use client'

import { useQuery, useInfiniteQuery } from '@tanstack/react-query'
import { eventsApi } from '@/lib/api'
import type { IdmEvent, IdmEventsResponse } from '@/types/api'

interface UseIdmEventsOptions {
  category?: string
  limit?: number
}

export function useIdmEvents(options: UseIdmEventsOptions = {}) {
  const { category, limit = 20 } = options

  return useQuery<IdmEventsResponse>({
    queryKey: ['events', { category, limit }],
    queryFn: () => eventsApi.list({ category, limit }),
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 10000,
  })
}

export function useInfiniteIdmEvents(options: UseIdmEventsOptions = {}) {
  const { category, limit = 20 } = options

  return useInfiniteQuery<IdmEventsResponse>({
    queryKey: ['events', 'infinite', { category, limit }],
    queryFn: ({ pageParam = 0 }) =>
      eventsApi.list({ category, limit, offset: pageParam as number }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      const totalFetched = allPages.reduce((sum, page) => sum + page.events.length, 0)
      if (totalFetched >= lastPage.total) return undefined
      return totalFetched
    },
    refetchInterval: 60000,
    staleTime: 30000,
  })
}

export function useIdmEvent(eventId: string) {
  return useQuery<IdmEvent>({
    queryKey: ['events', eventId],
    queryFn: () => eventsApi.getById(eventId),
    enabled: !!eventId,
  })
}

export function useEventCategories() {
  return useQuery({
    queryKey: ['events', 'categories'],
    queryFn: () => eventsApi.categories(),
    staleTime: 60000,
  })
}

export function useEventStats() {
  return useQuery({
    queryKey: ['events', 'stats'],
    queryFn: () => eventsApi.stats(),
    refetchInterval: 60000,
    staleTime: 30000,
  })
}
