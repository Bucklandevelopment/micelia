'use client'

import { useQuery } from '@tanstack/react-query'
import { energyApi } from '@/lib/api'
import type { EnergyUIData, EnergyState } from '@/types/api'

export function useEnergyStatus() {
  return useQuery<EnergyUIData>({
    queryKey: ['energy', 'status'],
    queryFn: () => energyApi.getStatus(),
    refetchInterval: 30000, // Refresh every 30 seconds
    staleTime: 10000, // Consider stale after 10 seconds
  })
}

export function useEnergyState() {
  return useQuery<{ current_state: EnergyState; recommendations: string[] }>({
    queryKey: ['energy', 'state'],
    queryFn: () => energyApi.getState(),
    refetchInterval: 30000,
    staleTime: 10000,
  })
}

export function useEnergyHistory(hours = 24) {
  return useQuery({
    queryKey: ['energy', 'history', hours],
    queryFn: () => energyApi.getHistory(hours),
    refetchInterval: 60000, // Refresh every minute
    staleTime: 30000,
  })
}

export function useComputeRecommendation() {
  return useQuery({
    queryKey: ['energy', 'compute-recommendation'],
    queryFn: () => energyApi.getComputeRecommendation(),
    refetchInterval: 60000,
    staleTime: 30000,
  })
}
