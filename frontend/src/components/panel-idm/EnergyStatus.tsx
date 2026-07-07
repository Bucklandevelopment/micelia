'use client'

import { useEnergyStatus } from '@/hooks/useEnergyStatus'
import { Battery, BatteryCharging, Sun, Wifi, WifiOff, Zap, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'
import type { EnergyState } from '@/types/api'

// State colors for different energy states (lowercase keys to match API)
const stateColors: Record<EnergyState, string> = {
  abundant: 'text-energy-abundant border-energy-abundant/30 bg-energy-abundant/10',
  normal: 'text-energy-normal border-energy-normal/30 bg-energy-normal/10',
  conserving: 'text-energy-conserving border-energy-conserving/30 bg-energy-conserving/10',
  critical: 'text-energy-critical border-energy-critical/30 bg-energy-critical/10',
  survival: 'text-energy-survival border-energy-survival/30 bg-energy-survival/10',
}

const stateDescriptions: Record<EnergyState, string> = {
  abundant: 'Energia abundante - Todas las operaciones habilitadas',
  normal: 'Operacion normal - Sistema funcionando correctamente',
  conserving: 'Modo conservacion - Reduciendo consumo',
  critical: 'Estado critico - Solo operaciones esenciales',
  survival: 'Modo supervivencia - Preservando datos',
}

const stateLabels: Record<EnergyState, string> = {
  abundant: 'ABUNDANT',
  normal: 'NORMAL',
  conserving: 'CONSERVING',
  critical: 'CRITICAL',
  survival: 'SURVIVAL',
}

const stateBgColors: Record<EnergyState, string> = {
  abundant: 'bg-energy-abundant/20',
  normal: 'bg-energy-normal/20',
  conserving: 'bg-energy-conserving/20',
  critical: 'bg-energy-critical/20',
  survival: 'bg-energy-survival/20',
}

export function EnergyStatus() {
  const { data, isLoading, error } = useEnergyStatus()

  if (isLoading) {
    return (
      <div className="glass rounded-xl p-6 animate-pulse">
        <div className="h-32 bg-idm-surface rounded-lg"></div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="glass rounded-xl p-6 border border-red-500/30">
        <div className="flex items-center gap-3 text-red-400">
          <AlertTriangle className="w-5 h-5" />
          <span>Error al cargar estado de energia</span>
        </div>
      </div>
    )
  }

  const state: EnergyState = data.state || 'normal'
  const battery = data.battery || { level: 100, is_charging: false, time_remaining_minutes: 0 }
  const solar = data.solar || { available: false, production_watts: 0 }
  const network = data.network || { online: true, type: 'wifi' }
  const calculated = data.calculated || { estimated_runtime_hours: -1, energy_surplus: false }
  const recommendations = data.recommendations || []

  return (
    <div className={clsx(
      'glass rounded-xl p-6 border transition-all duration-500',
      stateColors[state]
    )}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={clsx('p-3 rounded-xl', stateBgColors[state])}>
            <Zap className={clsx(
              'w-6 h-6',
              state === 'critical' || state === 'survival' ? 'animate-pulse' : ''
            )} />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Estado de Energia</h2>
            <p className="text-sm opacity-70">{stateDescriptions[state]}</p>
          </div>
        </div>
        <div className={clsx(
          'px-4 py-2 rounded-full text-sm font-medium',
          stateColors[state]
        )}>
          {stateLabels[state]}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Battery */}
        <div className="bg-idm-surface/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            {battery.is_charging ? (
              <BatteryCharging className="w-4 h-4 text-energy-abundant" />
            ) : (
              <Battery className="w-4 h-4 text-gray-400" />
            )}
            <span className="text-sm text-gray-400">Bateria</span>
          </div>
          <div className="text-2xl font-bold">{battery.level}%</div>
          {battery.time_remaining_minutes > 0 && (
            <div className="text-xs text-gray-500">
              {Math.floor(battery.time_remaining_minutes / 60)}h {battery.time_remaining_minutes % 60}m restante
            </div>
          )}
          {/* Battery bar */}
          <div className="mt-2 h-2 bg-idm-border rounded-full overflow-hidden">
            <div
              className={clsx(
                'h-full rounded-full transition-all duration-500',
                battery.level > 50 ? 'bg-energy-abundant' :
                battery.level > 20 ? 'bg-energy-conserving' : 'bg-energy-critical'
              )}
              style={{ width: `${battery.level}%` }}
            />
          </div>
        </div>

        {/* Solar */}
        <div className="bg-idm-surface/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Sun className={clsx(
              'w-4 h-4',
              solar.available ? 'text-energy-conserving' : 'text-gray-400'
            )} />
            <span className="text-sm text-gray-400">Solar</span>
          </div>
          <div className="text-2xl font-bold">
            {solar.available ? `${solar.production_watts}W` : '--'}
          </div>
          <div className="text-xs text-gray-500">
            {solar.available ? 'Produccion activa' : 'No disponible'}
          </div>
        </div>

        {/* Network */}
        <div className="bg-idm-surface/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            {network.online ? (
              <Wifi className="w-4 h-4 text-energy-abundant" />
            ) : (
              <WifiOff className="w-4 h-4 text-energy-critical" />
            )}
            <span className="text-sm text-gray-400">Red</span>
          </div>
          <div className="text-2xl font-bold">
            {network.online ? 'Online' : 'Offline'}
          </div>
          <div className="text-xs text-gray-500 capitalize">{network.type}</div>
        </div>

        {/* Runtime */}
        <div className="bg-idm-surface/50 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-idm-primary" />
            <span className="text-sm text-gray-400">Runtime</span>
          </div>
          <div className="text-2xl font-bold">
            {calculated.estimated_runtime_hours === Infinity
              ? '∞'
              : calculated.estimated_runtime_hours > 0
                ? `${calculated.estimated_runtime_hours.toFixed(1)}h`
                : '--'}
          </div>
          <div className="text-xs text-gray-500">
            {calculated.energy_surplus ? 'Excedente de energia' : 'Consumiendo bateria'}
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div className="mt-4 pt-4 border-t border-idm-border/50">
          <div className="text-sm text-gray-400 mb-2">Recomendaciones:</div>
          <div className="flex flex-wrap gap-2">
            {recommendations.map((rec, idx) => (
              <span key={idx} className="text-xs px-2 py-1 bg-idm-surface rounded-full text-gray-300">
                {rec}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
