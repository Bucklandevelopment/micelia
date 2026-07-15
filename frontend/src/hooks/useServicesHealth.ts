'use client'

import { useQuery } from '@tanstack/react-query'
import { healthApi } from '@/lib/api'
import type { RegistryServiceStatus } from '@/lib/services'

/**
 * Salud viva de los dominios que el registry del gateway monitoriza.
 *
 * Envuelve `GET /api/v1/health/services` (mismo patrón que `usePipelineStatus`).
 * Devuelve el mapa `{ health|research|education|security: RegistryServiceStatus }`.
 * Refetch cada 15s para que los badges de la página `/servicios` reflejen el estado
 * real sin recargar.
 */
export function useServicesHealth() {
  return useQuery<Record<string, RegistryServiceStatus>>({
    queryKey: ['health', 'services'],
    queryFn: async () => {
      const res = await healthApi.services()
      return (res.services ?? {}) as Record<string, RegistryServiceStatus>
    },
    refetchInterval: 15000,
    staleTime: 10000,
  })
}
