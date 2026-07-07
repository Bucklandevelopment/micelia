'use client'

import { useIdmEvents } from '@/hooks/useIdmEvents'
import { Clock, Activity, Heart, GraduationCap, Fingerprint, Shield, Zap, AlertTriangle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'
import { clsx } from 'clsx'
import type { IdmEvent } from '@/types/api'

const categoryIcons: Record<string, React.ReactNode> = {
  health: <Heart className="w-4 h-4" />,
  education: <GraduationCap className="w-4 h-4" />,
  identity: <Fingerprint className="w-4 h-4" />,
  system: <Zap className="w-4 h-4" />,
  security: <Shield className="w-4 h-4" />,
}

const categoryColors: Record<string, string> = {
  health: 'text-idm-health bg-idm-health/10 border-idm-health/30',
  education: 'text-idm-education bg-idm-education/10 border-idm-education/30',
  identity: 'text-idm-identity bg-idm-identity/10 border-idm-identity/30',
  system: 'text-idm-primary bg-idm-primary/10 border-idm-primary/30',
  security: 'text-orange-400 bg-orange-400/10 border-orange-400/30',
}

export function EventTimeline() {
  const { data, isLoading, error } = useIdmEvents()

  const events: IdmEvent[] = data?.events || []

  const formatEventType = (type: string) => {
    // Convert event_type like "system.energy.state_changed" to "Energy State Changed"
    const parts = type.split('.')
    return parts
      .slice(1)
      .join(' ')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase())
  }

  return (
    <div className="glass rounded-xl p-6 border border-idm-border">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-idm-primary/10">
            <Activity className="w-5 h-5 text-idm-primary" />
          </div>
          <div>
            <h2 className="text-lg font-semibold">Eventos Recientes</h2>
            <p className="text-xs text-gray-500">Ultimas 24 horas</p>
          </div>
        </div>
        <span className="text-xs text-gray-500">{events.length} eventos</span>
      </div>

      {/* Events List */}
      <div className="space-y-3 max-h-[400px] overflow-y-auto">
        {isLoading ? (
          <div className="text-center py-8 text-gray-500">
            <Activity className="w-8 h-8 mx-auto mb-2 animate-pulse" />
            <p>Cargando eventos...</p>
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-400">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
            <p>Error al cargar eventos</p>
          </div>
        ) : events.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Clock className="w-8 h-8 mx-auto mb-2" />
            <p>No hay eventos recientes</p>
          </div>
        ) : (
          events.map((event) => (
            <div
              key={event.event_id}
              className="flex items-start gap-3 p-3 rounded-lg bg-idm-surface/50 hover:bg-idm-surface transition-colors"
            >
              {/* Category Icon */}
              <div className={clsx(
                'p-2 rounded-lg border',
                categoryColors[event.category] || 'text-gray-400 bg-gray-700/50 border-gray-600'
              )}>
                {categoryIcons[event.category] || <Activity className="w-4 h-4" />}
              </div>

              {/* Event Details */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium">
                    {formatEventType(event.event_type)}
                  </span>
                  <span className={clsx(
                    'px-1.5 py-0.5 rounded text-xs',
                    event.action === 'create' && 'bg-green-500/20 text-green-400',
                    event.action === 'update' && 'bg-blue-500/20 text-blue-400',
                    event.action === 'delete' && 'bg-red-500/20 text-red-400',
                    event.action === 'alert' && 'bg-orange-500/20 text-orange-400',
                    event.action === 'audit' && 'bg-purple-500/20 text-purple-400',
                    !['create', 'update', 'delete', 'alert', 'audit'].includes(event.action) && 'bg-gray-500/20 text-gray-400'
                  )}>
                    {event.action}
                  </span>
                </div>
                <div className="text-xs text-gray-500 truncate">
                  {event.source} • {Object.keys(event.payload || {}).length} campos
                </div>
              </div>

              {/* Timestamp */}
              <div className="text-xs text-gray-500 whitespace-nowrap">
                <Clock className="w-3 h-3 inline mr-1" />
                {formatDistanceToNow(new Date(event.timestamp), {
                  addSuffix: true,
                  locale: es
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* View All Link */}
      {events.length > 0 && (
        <div className="mt-4 pt-4 border-t border-idm-border text-center">
          <button className="text-sm text-idm-primary hover:text-idm-primary/80 transition-colors">
            Ver todos los eventos
          </button>
        </div>
      )}
    </div>
  )
}
