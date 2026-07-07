'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Shield, Server, Cpu, Wifi, Battery, Sun, Key, Save, RefreshCw,
  AlertTriangle, Check, Loader2, HardDrive
} from 'lucide-react'
import { clsx } from 'clsx'

interface SystemConfig {
  // Compute Router
  preferLocal: boolean
  allowCloudForSensitiveData: boolean
  maxCloudCostPerDay: number

  // Energy Thresholds
  solarPriorityThreshold: number
  batteryConserveThreshold: number
  batteryCriticalThreshold: number

  // Security
  osascriptEnabled: boolean
  osascriptRequireAuth: boolean
  apiKeyRotationDays: number

  // Local Services
  ollamaEnabled: boolean
  ollamaDefaultModel: string
  codkingEnabled: boolean
}

async function fetchSystemConfig(): Promise<SystemConfig> {
  const response = await fetch('/api/v1/config')
  if (!response.ok) {
    // Default config if endpoint doesn't exist
    return {
      preferLocal: true,
      allowCloudForSensitiveData: false,
      maxCloudCostPerDay: 0,
      solarPriorityThreshold: 80,
      batteryConserveThreshold: 50,
      batteryCriticalThreshold: 20,
      osascriptEnabled: true,
      osascriptRequireAuth: true,
      apiKeyRotationDays: 90,
      ollamaEnabled: true,
      ollamaDefaultModel: 'llama3.1:8b',
      codkingEnabled: true
    }
  }
  return response.json()
}

async function saveSystemConfig(config: Partial<SystemConfig>): Promise<void> {
  const response = await fetch('/api/v1/config', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  })
  if (!response.ok) {
    throw new Error('Failed to save configuration')
  }
}

export function SystemSettings() {
  const queryClient = useQueryClient()
  const [hasChanges, setHasChanges] = useState(false)
  const [localConfig, setLocalConfig] = useState<Partial<SystemConfig>>({})

  const { data: config, isLoading } = useQuery({
    queryKey: ['system', 'config'],
    queryFn: fetchSystemConfig
  })

  const saveMutation = useMutation({
    mutationFn: saveSystemConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system', 'config'] })
      setHasChanges(false)
      setLocalConfig({})
    }
  })

  const updateConfig = (key: keyof SystemConfig, value: unknown) => {
    setLocalConfig(prev => ({ ...prev, [key]: value }))
    setHasChanges(true)
  }

  const getConfigValue = <K extends keyof SystemConfig>(key: K): SystemConfig[K] => {
    return (localConfig[key] ?? config?.[key]) as SystemConfig[K]
  }

  const handleSave = () => {
    saveMutation.mutate(localConfig)
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
      {/* Save Banner */}
      {hasChanges && (
        <div className="glass rounded-xl p-4 border border-idm-primary/30 bg-idm-primary/5 sticky top-20 z-10">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-idm-primary" />
              <span className="text-sm">Tienes cambios sin guardar</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setLocalConfig({})
                  setHasChanges(false)
                }}
                className="px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Descartar
              </button>
              <button
                onClick={handleSave}
                disabled={saveMutation.isPending}
                className="flex items-center gap-2 px-4 py-1.5 bg-idm-primary text-white rounded-lg text-sm hover:bg-idm-primary/80 transition-colors disabled:opacity-50"
              >
                {saveMutation.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Compute Router Settings */}
      <div className="glass rounded-xl border border-idm-border overflow-hidden">
        <div className="p-4 border-b border-idm-border bg-idm-surface/50">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-idm-primary" />
            <h3 className="font-medium">Compute Router</h3>
          </div>
        </div>
        <div className="p-4 space-y-4">
          {/* Prefer Local */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">Preferir computo local</div>
              <div className="text-xs text-gray-500">Usar Ollama/CodKing antes que cloud cuando sea posible</div>
            </div>
            <button
              onClick={() => updateConfig('preferLocal', !getConfigValue('preferLocal'))}
              className={clsx(
                'relative w-12 h-6 rounded-full transition-colors',
                getConfigValue('preferLocal') ? 'bg-energy-abundant' : 'bg-idm-surface'
              )}
            >
              <div className={clsx(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                getConfigValue('preferLocal') ? 'translate-x-7' : 'translate-x-1'
              )} />
            </button>
          </div>

          {/* Cloud for Sensitive Data */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">Permitir cloud para datos sensibles</div>
              <div className="text-xs text-gray-500">Si desactivado, datos de salud siempre van local</div>
            </div>
            <button
              onClick={() => updateConfig('allowCloudForSensitiveData', !getConfigValue('allowCloudForSensitiveData'))}
              className={clsx(
                'relative w-12 h-6 rounded-full transition-colors',
                getConfigValue('allowCloudForSensitiveData') ? 'bg-energy-conserving' : 'bg-idm-surface'
              )}
            >
              <div className={clsx(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                getConfigValue('allowCloudForSensitiveData') ? 'translate-x-7' : 'translate-x-1'
              )} />
            </button>
          </div>

          {/* Max Cloud Cost */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-sm">Limite de costo cloud diario</div>
                <div className="text-xs text-gray-500">0 = solo free tier</div>
              </div>
              <span className="text-sm font-mono">${getConfigValue('maxCloudCostPerDay')}</span>
            </div>
            <input
              type="range"
              min="0"
              max="50"
              step="1"
              value={getConfigValue('maxCloudCostPerDay')}
              onChange={(e) => updateConfig('maxCloudCostPerDay', parseInt(e.target.value))}
              className="w-full h-2 bg-idm-surface rounded-lg appearance-none cursor-pointer accent-idm-primary"
            />
          </div>
        </div>
      </div>

      {/* Energy Thresholds */}
      <div className="glass rounded-xl border border-idm-border overflow-hidden">
        <div className="p-4 border-b border-idm-border bg-idm-surface/50">
          <div className="flex items-center gap-3">
            <Battery className="w-5 h-5 text-energy-conserving" />
            <h3 className="font-medium">Umbrales de Energia</h3>
          </div>
        </div>
        <div className="p-4 space-y-4">
          {/* Solar Priority */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Sun className="w-4 h-4 text-yellow-400" />
                <div>
                  <div className="font-medium text-sm">Prioridad solar</div>
                  <div className="text-xs text-gray-500">Usar local cuando bateria &gt; umbral con solar</div>
                </div>
              </div>
              <span className="text-sm font-mono">{getConfigValue('solarPriorityThreshold')}%</span>
            </div>
            <input
              type="range"
              min="50"
              max="100"
              value={getConfigValue('solarPriorityThreshold')}
              onChange={(e) => updateConfig('solarPriorityThreshold', parseInt(e.target.value))}
              className="w-full h-2 bg-idm-surface rounded-lg appearance-none cursor-pointer accent-yellow-400"
            />
          </div>

          {/* Battery Conserve */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-sm">Modo conservacion</div>
                <div className="text-xs text-gray-500">Preferir cloud cuando bateria &lt; umbral</div>
              </div>
              <span className="text-sm font-mono">{getConfigValue('batteryConserveThreshold')}%</span>
            </div>
            <input
              type="range"
              min="20"
              max="80"
              value={getConfigValue('batteryConserveThreshold')}
              onChange={(e) => updateConfig('batteryConserveThreshold', parseInt(e.target.value))}
              className="w-full h-2 bg-idm-surface rounded-lg appearance-none cursor-pointer accent-energy-conserving"
            />
          </div>

          {/* Battery Critical */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <div className="font-medium text-sm">Modo critico</div>
                <div className="text-xs text-gray-500">Solo tareas esenciales cuando bateria &lt; umbral</div>
              </div>
              <span className="text-sm font-mono">{getConfigValue('batteryCriticalThreshold')}%</span>
            </div>
            <input
              type="range"
              min="5"
              max="30"
              value={getConfigValue('batteryCriticalThreshold')}
              onChange={(e) => updateConfig('batteryCriticalThreshold', parseInt(e.target.value))}
              className="w-full h-2 bg-idm-surface rounded-lg appearance-none cursor-pointer accent-energy-critical"
            />
          </div>
        </div>
      </div>

      {/* Security Settings */}
      <div className="glass rounded-xl border border-idm-border overflow-hidden">
        <div className="p-4 border-b border-idm-border bg-idm-surface/50">
          <div className="flex items-center gap-3">
            <Shield className="w-5 h-5 text-orange-400" />
            <h3 className="font-medium">Seguridad</h3>
          </div>
        </div>
        <div className="p-4 space-y-4">
          {/* OSASCRIPT Enabled */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">OSASCRIPT habilitado</div>
              <div className="text-xs text-gray-500">Permite control del sistema via AppleScript</div>
            </div>
            <button
              onClick={() => updateConfig('osascriptEnabled', !getConfigValue('osascriptEnabled'))}
              className={clsx(
                'relative w-12 h-6 rounded-full transition-colors',
                getConfigValue('osascriptEnabled') ? 'bg-energy-abundant' : 'bg-idm-surface'
              )}
            >
              <div className={clsx(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                getConfigValue('osascriptEnabled') ? 'translate-x-7' : 'translate-x-1'
              )} />
            </button>
          </div>

          {/* OSASCRIPT Auth Required */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">Requiere autenticacion</div>
              <div className="text-xs text-gray-500">API Key necesaria para operaciones OSASCRIPT</div>
            </div>
            <button
              onClick={() => updateConfig('osascriptRequireAuth', !getConfigValue('osascriptRequireAuth'))}
              className={clsx(
                'relative w-12 h-6 rounded-full transition-colors',
                getConfigValue('osascriptRequireAuth') ? 'bg-energy-abundant' : 'bg-idm-surface'
              )}
            >
              <div className={clsx(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                getConfigValue('osascriptRequireAuth') ? 'translate-x-7' : 'translate-x-1'
              )} />
            </button>
          </div>
        </div>
      </div>

      {/* Local Services */}
      <div className="glass rounded-xl border border-idm-border overflow-hidden">
        <div className="p-4 border-b border-idm-border bg-idm-surface/50">
          <div className="flex items-center gap-3">
            <HardDrive className="w-5 h-5 text-blue-400" />
            <h3 className="font-medium">Servicios Locales</h3>
          </div>
        </div>
        <div className="p-4 space-y-4">
          {/* Ollama */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">Ollama</div>
              <div className="text-xs text-gray-500">LLM local para inferencia privada</div>
            </div>
            <div className="flex items-center gap-3">
              <select
                value={getConfigValue('ollamaDefaultModel')}
                onChange={(e) => updateConfig('ollamaDefaultModel', e.target.value)}
                className="bg-idm-surface border border-idm-border rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-idm-primary"
              >
                <option value="llama3.1:8b">llama3.1:8b</option>
                <option value="llama3.2:3b">llama3.2:3b</option>
                <option value="mistral:7b">mistral:7b</option>
                <option value="codellama:13b">codellama:13b</option>
              </select>
              <button
                onClick={() => updateConfig('ollamaEnabled', !getConfigValue('ollamaEnabled'))}
                className={clsx(
                  'relative w-12 h-6 rounded-full transition-colors',
                  getConfigValue('ollamaEnabled') ? 'bg-energy-abundant' : 'bg-idm-surface'
                )}
              >
                <div className={clsx(
                  'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                  getConfigValue('ollamaEnabled') ? 'translate-x-7' : 'translate-x-1'
                )} />
              </button>
            </div>
          </div>

          {/* CodKing */}
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium text-sm">CodKing</div>
              <div className="text-xs text-gray-500">Cores especializados (salud, educacion, ciberseguridad)</div>
            </div>
            <button
              onClick={() => updateConfig('codkingEnabled', !getConfigValue('codkingEnabled'))}
              className={clsx(
                'relative w-12 h-6 rounded-full transition-colors',
                getConfigValue('codkingEnabled') ? 'bg-energy-abundant' : 'bg-idm-surface'
              )}
            >
              <div className={clsx(
                'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                getConfigValue('codkingEnabled') ? 'translate-x-7' : 'translate-x-1'
              )} />
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
