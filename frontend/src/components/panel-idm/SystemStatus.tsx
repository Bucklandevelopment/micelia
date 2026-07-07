'use client'

import { useSystemStatus } from '@/hooks/useSystemStatus'
import { Server, Database, Cpu, Bot, CheckCircle, XCircle, AlertCircle, Loader2, HardDrive, MemoryStick } from 'lucide-react'
import { clsx } from 'clsx'
import type { ServiceStatus } from '@/types/api'

export function SystemStatus() {
  const { data, isLoading, error } = useSystemStatus()

  const services: ServiceStatus[] = data?.services || [
    { name: 'micelia', status: 'unknown' },
    { name: 'Ollama', status: 'unknown' },
  ]

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-4 h-4 text-energy-abundant" />
      case 'unhealthy':
        return <XCircle className="w-4 h-4 text-energy-critical" />
      default:
        return <AlertCircle className="w-4 h-4 text-gray-500" />
    }
  }

  const getServiceIcon = (name: string) => {
    const lower = name.toLowerCase()
    if (lower.includes('postgres')) return <Database className="w-4 h-4" />
    if (lower.includes('redis')) return <Database className="w-4 h-4" />
    if (lower.includes('ollama')) return <Bot className="w-4 h-4" />
    if (lower.includes('idm')) return <Server className="w-4 h-4" />
    if (lower.includes('health') || lower.includes('research') || lower.includes('education') || lower.includes('security'))
      return <Server className="w-4 h-4" />
    return <Cpu className="w-4 h-4" />
  }

  return (
    <div className="glass rounded-xl p-6 border border-idm-border h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-idm-primary/10">
            <Server className="w-5 h-5 text-idm-primary" />
          </div>
          <h2 className="text-lg font-semibold">Sistema</h2>
        </div>
        {isLoading && <Loader2 className="w-4 h-4 text-gray-500 animate-spin" />}
      </div>

      {/* Services List */}
      <div className="space-y-2">
        {services.map((service, idx) => (
          <div
            key={idx}
            className={clsx(
              'flex items-center justify-between p-3 rounded-lg transition-colors',
              service.status === 'healthy' ? 'bg-energy-abundant/5' :
              service.status === 'unhealthy' ? 'bg-energy-critical/5' :
              'bg-idm-surface/50'
            )}
          >
            <div className="flex items-center gap-3">
              <span className="text-gray-400">{getServiceIcon(service.name)}</span>
              <span className="text-sm">{service.name}</span>
            </div>
            <div className="flex items-center gap-2">
              {service.latency && (
                <span className="text-xs text-gray-500">{service.latency}ms</span>
              )}
              {getStatusIcon(service.status)}
            </div>
          </div>
        ))}
      </div>

      {/* Resources */}
      {data?.resources && (
        <div className="mt-4 pt-4 border-t border-idm-border">
          <div className="text-xs text-gray-500 mb-2">Recursos</div>
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-idm-surface/50 rounded-lg p-2 text-center">
              <Cpu className="w-4 h-4 mx-auto mb-1 text-gray-400" />
              <div className="text-sm font-medium">{data.resources.cpu_percent.toFixed(0)}%</div>
              <div className="text-xs text-gray-500">CPU</div>
            </div>
            <div className="bg-idm-surface/50 rounded-lg p-2 text-center">
              <MemoryStick className="w-4 h-4 mx-auto mb-1 text-gray-400" />
              <div className="text-sm font-medium">{data.resources.memory_percent.toFixed(0)}%</div>
              <div className="text-xs text-gray-500">RAM</div>
            </div>
            <div className="bg-idm-surface/50 rounded-lg p-2 text-center">
              <HardDrive className="w-4 h-4 mx-auto mb-1 text-gray-400" />
              <div className="text-sm font-medium">{data.resources.disk_percent.toFixed(0)}%</div>
              <div className="text-xs text-gray-500">Disco</div>
            </div>
          </div>
        </div>
      )}

      {/* OSASCRIPT Status */}
      <div className="mt-4 pt-4 border-t border-idm-border">
        <div className="text-xs text-gray-500 mb-2">OSASCRIPT Module</div>
        <div className="flex items-center gap-2">
          <div className={clsx(
            'px-2 py-1 rounded text-xs',
            data?.osascript?.enabled
              ? 'bg-energy-abundant/20 text-energy-abundant'
              : 'bg-gray-700 text-gray-400'
          )}>
            {data?.osascript?.enabled ? 'Enabled' : 'Disabled'}
          </div>
          {data?.osascript?.require_auth && (
            <div className="px-2 py-1 rounded text-xs bg-idm-primary/20 text-idm-primary">
              Auth Required
            </div>
          )}
        </div>
      </div>

      {/* AI Status */}
      <div className="mt-4 pt-4 border-t border-idm-border">
        <div className="text-xs text-gray-500 mb-2">AI Engine ({data?.ai?.models?.length || 0} modelos)</div>
        <div className="flex flex-wrap gap-2 max-h-20 overflow-y-auto">
          {(data?.ai?.models || []).slice(0, 5).map((model: string, idx: number) => (
            <div
              key={idx}
              className="px-2 py-1 rounded text-xs bg-idm-education/10 text-idm-education"
            >
              {model}
            </div>
          ))}
          {(data?.ai?.models?.length || 0) > 5 && (
            <div className="px-2 py-1 rounded text-xs bg-gray-700 text-gray-400">
              +{(data?.ai?.models?.length || 0) - 5} más
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
