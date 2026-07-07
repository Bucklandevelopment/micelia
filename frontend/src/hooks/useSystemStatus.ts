'use client'

import { useQuery } from '@tanstack/react-query'
import { healthApi, aiApi } from '@/lib/api'
import type { ServiceStatus, SystemStatusData, HealthDetailedResponse, AIStatusResponse } from '@/types/api'

export function useSystemStatus() {
  return useQuery<SystemStatusData>({
    queryKey: ['system', 'status'],
    queryFn: async () => {
      const startTime = Date.now()

      try {
        // Fetch health check and AI status in parallel
        const [healthResponse, aiResponse] = await Promise.allSettled([
          healthApi.detailed(),
          aiApi.status()
        ])

        const latency = Date.now() - startTime

        // Parse health response
        const services: ServiceStatus[] = []

        // Add micelia status
        services.push({
          name: 'micelia',
          status: healthResponse.status === 'fulfilled' ? 'healthy' : 'unhealthy',
          latency
        })

        // Add other services from health check if available
        if (healthResponse.status === 'fulfilled') {
          const healthData = healthResponse.value as HealthDetailedResponse

          // Add services from detailed health check
          if (healthData.services) {
            for (const [name, service] of Object.entries(healthData.services)) {
              services.push({
                name: name.charAt(0).toUpperCase() + name.slice(1),
                status: service.healthy ? 'healthy' : 'unhealthy',
                latency: service.latency_ms ?? undefined
              })
            }
          }
        }

        // Add Ollama status from AI response
        if (aiResponse.status === 'fulfilled') {
          const aiData = aiResponse.value as AIStatusResponse
          services.push({
            name: 'Ollama',
            status: aiData.ollama?.available ? 'healthy' : 'unhealthy'
          })
        } else {
          services.push({ name: 'Ollama', status: 'unknown' })
        }

        // Get resources if available
        let resources
        if (healthResponse.status === 'fulfilled') {
          const healthData = healthResponse.value as HealthDetailedResponse
          if (healthData.resources) {
            resources = {
              cpu_percent: healthData.resources.cpu_percent,
              memory_percent: healthData.resources.memory.percent,
              disk_percent: healthData.resources.disk.percent
            }
          }
        }

        return {
          services,
          osascript: {
            enabled: true,
            require_auth: true
          },
          ai: {
            models: aiResponse.status === 'fulfilled'
              ? (aiResponse.value as AIStatusResponse).ollama?.models || []
              : []
          },
          resources
        }
      } catch (error) {
        // Return default state on error
        return {
          services: [
            { name: 'micelia', status: 'unhealthy' as const },
            { name: 'Ollama', status: 'unknown' as const },
          ],
          osascript: {
            enabled: false,
            require_auth: false
          },
          ai: {
            models: []
          }
        }
      }
    },
    refetchInterval: 30000,
    staleTime: 15000,
  })
}

export function useHealthDetailed() {
  return useQuery<HealthDetailedResponse>({
    queryKey: ['health', 'detailed'],
    queryFn: () => healthApi.detailed(),
    refetchInterval: 30000,
    staleTime: 15000,
  })
}

export function useAIStatus() {
  return useQuery<AIStatusResponse>({
    queryKey: ['ai', 'status'],
    queryFn: () => aiApi.status(),
    refetchInterval: 60000,
    staleTime: 30000,
  })
}
