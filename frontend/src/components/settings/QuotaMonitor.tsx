'use client'

import { useQuery } from '@tanstack/react-query'
import { Gauge, TrendingUp, AlertTriangle, Clock, Zap, Brain, Database, Server } from 'lucide-react'
import { clsx } from 'clsx'

interface QuotaUsage {
  provider_id: string
  provider_name: string
  category: string
  used: number
  limit: number
  unit: string
  reset_time: string
  percentage: number
  is_exhausted: boolean
}

interface UsageStats {
  today: {
    requests: number
    tokens: number
    cost_equivalent_usd: number
  }
  thisMonth: {
    requests: number
    tokens: number
    cost_equivalent_usd: number
  }
  quotas: QuotaUsage[]
}

async function fetchUsageStats(): Promise<UsageStats> {
  const response = await fetch('/api/v1/frangels/usage')
  if (!response.ok) {
    // Return mock data if endpoint doesn't exist yet
    return {
      today: { requests: 0, tokens: 0, cost_equivalent_usd: 0 },
      thisMonth: { requests: 0, tokens: 0, cost_equivalent_usd: 0 },
      quotas: []
    }
  }
  return response.json()
}

export function QuotaMonitor() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['frangels', 'usage'],
    queryFn: fetchUsageStats,
    refetchInterval: 30000
  })

  const getCategoryIcon = (category: string) => {
    const icons: Record<string, typeof Brain> = {
      inference: Brain,
      gpu: Zap,
      database: Database,
      infra: Server
    }
    return icons[category] || Server
  }

  const getUsageColor = (percentage: number) => {
    if (percentage >= 90) return 'text-energy-critical bg-energy-critical'
    if (percentage >= 70) return 'text-energy-conserving bg-energy-conserving'
    return 'text-energy-abundant bg-energy-abundant'
  }

  if (isLoading) {
    return (
      <div className="glass rounded-xl p-6 animate-pulse">
        <div className="h-64 bg-idm-surface rounded-lg"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Usage Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass rounded-xl p-4 border border-idm-border">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-idm-primary/10">
              <TrendingUp className="w-5 h-5 text-idm-primary" />
            </div>
            <span className="text-sm text-gray-400">Hoy</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-xs text-gray-500">Requests</span>
              <span className="text-sm font-medium">{stats?.today.requests.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-gray-500">Tokens</span>
              <span className="text-sm font-medium">{stats?.today.tokens.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-idm-border">
              <span className="text-xs text-gray-500">Valor equivalente</span>
              <span className="text-sm font-medium text-energy-abundant">
                ${stats?.today.cost_equivalent_usd.toFixed(2) || '0.00'}
              </span>
            </div>
          </div>
        </div>

        <div className="glass rounded-xl p-4 border border-idm-border">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-idm-education/10">
              <Gauge className="w-5 h-5 text-idm-education" />
            </div>
            <span className="text-sm text-gray-400">Este mes</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-xs text-gray-500">Requests</span>
              <span className="text-sm font-medium">{stats?.thisMonth.requests.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-gray-500">Tokens</span>
              <span className="text-sm font-medium">{stats?.thisMonth.tokens.toLocaleString() || 0}</span>
            </div>
            <div className="flex justify-between pt-2 border-t border-idm-border">
              <span className="text-xs text-gray-500">Valor equivalente</span>
              <span className="text-sm font-medium text-energy-abundant">
                ${stats?.thisMonth.cost_equivalent_usd.toFixed(2) || '0.00'}
              </span>
            </div>
          </div>
        </div>

        <div className="glass rounded-xl p-4 border border-idm-border">
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2 rounded-lg bg-energy-abundant/10">
              <Zap className="w-5 h-5 text-energy-abundant" />
            </div>
            <span className="text-sm text-gray-400">Capacidad total</span>
          </div>
          <div className="text-center py-2">
            <div className="text-3xl font-bold text-energy-abundant">~$650</div>
            <div className="text-xs text-gray-500 mt-1">valor mensual en free tiers</div>
          </div>
        </div>
      </div>

      {/* Quota Details */}
      <div className="glass rounded-xl border border-idm-border overflow-hidden">
        <div className="p-4 border-b border-idm-border bg-idm-surface/50">
          <div className="flex items-center gap-3">
            <Gauge className="w-5 h-5 text-idm-primary" />
            <h3 className="font-medium">Uso de Cuotas por Proveedor</h3>
          </div>
        </div>

        {stats?.quotas && stats.quotas.length > 0 ? (
          <div className="divide-y divide-idm-border">
            {stats.quotas.map((quota) => {
              const Icon = getCategoryIcon(quota.category)
              return (
                <div key={quota.provider_id} className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <Icon className="w-4 h-4 text-gray-400" />
                      <span className="font-medium">{quota.provider_name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-400">
                        {quota.used.toLocaleString()} / {quota.limit.toLocaleString()} {quota.unit}
                      </span>
                      <span className={clsx(
                        'px-2 py-0.5 rounded text-xs',
                        getUsageColor(quota.percentage).replace('bg-', 'bg-').replace('text-', 'text-')
                      )}>
                        {quota.percentage.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  {/* Progress Bar */}
                  <div className="h-2 bg-idm-surface rounded-full overflow-hidden">
                    <div
                      className={clsx(
                        'h-full rounded-full transition-all duration-500',
                        quota.percentage >= 90 ? 'bg-energy-critical' :
                        quota.percentage >= 70 ? 'bg-energy-conserving' :
                        'bg-energy-abundant'
                      )}
                      style={{ width: `${Math.min(quota.percentage, 100)}%` }}
                    />
                  </div>
                  {/* Reset Time */}
                  <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
                    <Clock className="w-3 h-3" />
                    <span>Reset: {quota.reset_time}</span>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500">
            <Gauge className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>No hay proveedores configurados aun</p>
            <p className="text-sm mt-1">Configura tus API keys en la pestana &quot;Proveedores Cloud&quot;</p>
          </div>
        )}
      </div>

      {/* Alerts */}
      {stats?.quotas && stats.quotas.some(q => q.percentage >= 80) && (
        <div className="glass rounded-xl p-4 border border-energy-conserving/30 bg-energy-conserving/5">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-energy-conserving mt-0.5" />
            <div>
              <h3 className="font-medium text-energy-conserving">Cuotas cercanas al limite</h3>
              <p className="text-sm text-gray-400 mt-1">
                Algunos proveedores estan cerca de agotar su cuota gratuita.
                El sistema automaticamente rotara a proveedores alternativos.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
