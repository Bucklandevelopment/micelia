'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Cloud, Key, Check, X, AlertTriangle, Loader2, Eye, EyeOff,
  Zap, Brain, Database, Server, ExternalLink, RefreshCw, Plus, Trash2
} from 'lucide-react'
import { clsx } from 'clsx'

// Provider definition type
interface ProviderDef {
  id: string
  name: string
  tier: string
  envKey: string
  extraKey?: string
  freeQuota: string
  url: string
}

interface CategoryDef {
  label: string
  icon: typeof Brain
  color: string
  providers: ProviderDef[]
}

// Provider categories and their providers
const PROVIDER_CATEGORIES: Record<string, CategoryDef> = {
  inference: {
    label: 'LLM Inference',
    icon: Brain,
    color: 'text-purple-400',
    providers: [
      { id: 'groq', name: 'Groq', tier: 'premium', envKey: 'GROQ_API_KEY', freeQuota: '14,400 req/dia', url: 'https://console.groq.com/keys' },
      { id: 'gemini', name: 'Google AI Studio', tier: 'premium', envKey: 'GOOGLE_AI_API_KEY', freeQuota: '1M tokens/dia', url: 'https://aistudio.google.com/apikey' },
      { id: 'deepseek', name: 'DeepSeek', tier: 'standard', envKey: 'DEEPSEEK_API_KEY', freeQuota: '5M tokens', url: 'https://platform.deepseek.com/' },
      { id: 'cohere', name: 'Cohere', tier: 'standard', envKey: 'COHERE_API_KEY', freeQuota: '1,000 req/mes', url: 'https://dashboard.cohere.com/api-keys' },
      { id: 'mistral', name: 'Mistral AI', tier: 'standard', envKey: 'MISTRAL_API_KEY', freeQuota: 'Trial tier', url: 'https://console.mistral.ai/api-keys/' },
      { id: 'openrouter', name: 'OpenRouter', tier: 'economy', envKey: 'OPENROUTER_API_KEY', freeQuota: 'Pay-per-use', url: 'https://openrouter.ai/keys' },
      { id: 'huggingface', name: 'HuggingFace', tier: 'economy', envKey: 'HUGGINGFACE_TOKEN', freeQuota: 'Unlimited (free models)', url: 'https://huggingface.co/settings/tokens' },
    ]
  },
  gpu: {
    label: 'GPU Computing',
    icon: Zap,
    color: 'text-yellow-400',
    providers: [
      { id: 'kaggle', name: 'Kaggle', tier: 'premium', envKey: 'KAGGLE_KEY', extraKey: 'KAGGLE_USERNAME', freeQuota: '30h GPU/sem', url: 'https://www.kaggle.com/settings' },
      { id: 'lightning', name: 'Lightning.ai', tier: 'standard', envKey: 'LIGHTNING_API_KEY', freeQuota: '22h GPU/mes', url: 'https://lightning.ai/' },
      { id: 'cloudflare_ai', name: 'Cloudflare AI', tier: 'economy', envKey: 'CLOUDFLARE_API_TOKEN', extraKey: 'CLOUDFLARE_ACCOUNT_ID', freeQuota: '100K req/dia', url: 'https://dash.cloudflare.com/' },
    ]
  },
  database: {
    label: 'Bases de Datos',
    icon: Database,
    color: 'text-blue-400',
    providers: [
      { id: 'qdrant', name: 'Qdrant Cloud', tier: 'premium', envKey: 'QDRANT_API_KEY', extraKey: 'QDRANT_URL', freeQuota: '1GB vectors', url: 'https://cloud.qdrant.io/' },
      { id: 'turso', name: 'Turso', tier: 'standard', envKey: 'TURSO_AUTH_TOKEN', extraKey: 'TURSO_DATABASE_URL', freeQuota: '9GB storage', url: 'https://turso.tech/' },
      { id: 'supabase', name: 'Supabase', tier: 'standard', envKey: 'SUPABASE_KEY', extraKey: 'SUPABASE_URL', freeQuota: '500MB + Auth', url: 'https://supabase.com/dashboard' },
      { id: 'upstash', name: 'Upstash Redis', tier: 'economy', envKey: 'UPSTASH_REDIS_TOKEN', extraKey: 'UPSTASH_REDIS_URL', freeQuota: '10K cmd/dia', url: 'https://console.upstash.com/' },
    ]
  },
  infra: {
    label: 'Infraestructura',
    icon: Server,
    color: 'text-green-400',
    providers: [
      { id: 'oracle', name: 'Oracle Cloud', tier: 'premium', envKey: 'ORACLE_FINGERPRINT', freeQuota: '4 ARM cores + 24GB', url: 'https://cloud.oracle.com/' },
      { id: 'vercel', name: 'Vercel', tier: 'standard', envKey: 'VERCEL_TOKEN', freeQuota: '100K func/mes', url: 'https://vercel.com/account/tokens' },
      { id: 'aws', name: 'AWS Lambda', tier: 'standard', envKey: 'AWS_SECRET_ACCESS_KEY', extraKey: 'AWS_ACCESS_KEY_ID', freeQuota: '1M req/mes', url: 'https://aws.amazon.com/console/' },
    ]
  }
}

interface ProviderStatus {
  id: string
  name: string
  configured: boolean
  enabled: boolean
  health: {
    is_available: boolean
    latency_ms: number
    last_error: string | null
  }
  quota: {
    used: number
    limit: number
    percentage: number
    is_exhausted: boolean
  } | null
  last_used: string | null
}

interface ProvidersResponse {
  providers: ProviderStatus[]
  by_category: Record<string, ProviderStatus[]>
  summary: {
    total: number
    configured: number
    enabled: number
  }
}

interface ProviderConfig {
  provider_id: string
  api_key: string
  extra_key?: string
  enabled: boolean
}

// API functions
async function fetchProviderStatus(): Promise<Record<string, ProviderStatus>> {
  try {
    const response = await fetch('/api/v1/frangels/providers')
    if (!response.ok) {
      // Return empty if endpoint doesn't exist yet
      return {}
    }
    const data: ProvidersResponse = await response.json()
    // Convert array to map by id for easy lookup
    const statusMap: Record<string, ProviderStatus> = {}
    for (const provider of data.providers) {
      statusMap[provider.id] = provider
    }
    return statusMap
  } catch {
    return {}
  }
}

async function saveProviderConfig(config: ProviderConfig): Promise<void> {
  const response = await fetch('/api/v1/frangels/providers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  })
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail || 'Failed to save provider configuration')
  }
}

async function testProvider(providerId: string): Promise<{ success: boolean; error?: string; latency_ms?: number }> {
  const response = await fetch(`/api/v1/frangels/providers/${providerId}/test`, {
    method: 'POST'
  })
  return response.json()
}

export function ProviderSettings() {
  const queryClient = useQueryClient()
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({})
  const [formData, setFormData] = useState<Record<string, { apiKey: string; extraKey?: string }>>({})

  const { data: providerStatus = {}, isLoading, refetch } = useQuery({
    queryKey: ['frangels', 'providers'],
    queryFn: fetchProviderStatus,
    refetchInterval: 60000
  })

  const saveMutation = useMutation({
    mutationFn: saveProviderConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['frangels', 'providers'] })
      setEditingProvider(null)
    }
  })

  const testMutation = useMutation({
    mutationFn: testProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['frangels', 'providers'] })
    }
  })

  const handleSave = (providerId: string) => {
    const data = formData[providerId]
    if (!data?.apiKey) return

    saveMutation.mutate({
      provider_id: providerId,
      api_key: data.apiKey,
      extra_key: data.extraKey,
      enabled: true
    })
  }

  const toggleShowKey = (providerId: string) => {
    setShowApiKey(prev => ({ ...prev, [providerId]: !prev[providerId] }))
  }

  const getTierBadge = (tier: string) => {
    const styles = {
      premium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      standard: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      economy: 'bg-gray-500/20 text-gray-400 border-gray-500/30'
    }
    return styles[tier as keyof typeof styles] || styles.economy
  }

  return (
    <div className="space-y-6">
      {/* Info Banner */}
      <div className="glass rounded-xl p-4 border border-idm-primary/30 bg-idm-primary/5">
        <div className="flex items-start gap-3">
          <Cloud className="w-5 h-5 text-idm-primary mt-0.5" />
          <div>
            <h3 className="font-medium text-idm-primary">Sistema Frangels - Free Angels</h3>
            <p className="text-sm text-gray-400 mt-1">
              Configura tus API keys para acceder a ~$650/mes en servicios cloud gratuitos.
              Los datos sensibles siempre se procesan localmente (Ollama).
            </p>
          </div>
        </div>
      </div>

      {/* Provider Categories */}
      {Object.entries(PROVIDER_CATEGORIES).map(([categoryId, category]) => (
        <div key={categoryId} className="glass rounded-xl border border-idm-border overflow-hidden">
          {/* Category Header */}
          <div className="p-4 border-b border-idm-border bg-idm-surface/50">
            <div className="flex items-center gap-3">
              <category.icon className={clsx('w-5 h-5', category.color)} />
              <h3 className="font-medium">{category.label}</h3>
              <span className="text-xs text-gray-500">
                {category.providers.filter(p => providerStatus[p.id]?.configured).length}/{category.providers.length} configurados
              </span>
            </div>
          </div>

          {/* Providers List */}
          <div className="divide-y divide-idm-border">
            {category.providers.map((provider) => {
              const status = providerStatus[provider.id]
              const isEditing = editingProvider === provider.id
              const form = formData[provider.id] || { apiKey: '', extraKey: '' }

              return (
                <div key={provider.id} className="p-4">
                  <div className="flex items-center justify-between">
                    {/* Provider Info */}
                    <div className="flex items-center gap-3">
                      <div className={clsx(
                        'w-2 h-2 rounded-full',
                        status?.configured && status?.health?.is_available ? 'bg-energy-abundant' :
                        status?.configured ? 'bg-energy-conserving' :
                        'bg-gray-600'
                      )} />
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{provider.name}</span>
                          <span className={clsx('px-2 py-0.5 rounded text-xs border', getTierBadge(provider.tier))}>
                            {provider.tier}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 mt-0.5">
                          <span className="font-mono">{provider.envKey}</span>
                          <span className="mx-2">•</span>
                          <span>{provider.freeQuota}</span>
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      {status?.configured && (
                        <button
                          onClick={() => testMutation.mutate(provider.id)}
                          disabled={testMutation.isPending}
                          className="p-2 rounded-lg hover:bg-idm-surface transition-colors"
                          title="Test connection"
                        >
                          {testMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
                          ) : (
                            <RefreshCw className="w-4 h-4 text-gray-400" />
                          )}
                        </button>
                      )}
                      <a
                        href={provider.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 rounded-lg hover:bg-idm-surface transition-colors"
                        title="Get API key"
                      >
                        <ExternalLink className="w-4 h-4 text-gray-400" />
                      </a>
                      <button
                        onClick={() => {
                          setEditingProvider(isEditing ? null : provider.id)
                          if (!isEditing) {
                            setFormData(prev => ({
                              ...prev,
                              [provider.id]: { apiKey: '', extraKey: '' }
                            }))
                          }
                        }}
                        className={clsx(
                          'px-3 py-1.5 rounded-lg text-sm transition-colors',
                          status?.configured
                            ? 'bg-idm-surface text-gray-400 hover:text-white'
                            : 'bg-idm-primary/20 text-idm-primary hover:bg-idm-primary/30'
                        )}
                      >
                        {status?.configured ? 'Editar' : 'Configurar'}
                      </button>
                    </div>
                  </div>

                  {/* Edit Form */}
                  {isEditing && (
                    <div className="mt-4 pt-4 border-t border-idm-border space-y-3">
                      {/* API Key Input */}
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">{provider.envKey}</label>
                        <div className="relative">
                          <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                          <input
                            type={showApiKey[provider.id] ? 'text' : 'password'}
                            value={form.apiKey}
                            onChange={(e) => setFormData(prev => ({
                              ...prev,
                              [provider.id]: { ...form, apiKey: e.target.value }
                            }))}
                            placeholder="sk-xxx... o AIzaSy..."
                            className="w-full pl-10 pr-10 py-2 bg-idm-surface border border-idm-border rounded-lg text-sm focus:outline-none focus:border-idm-primary"
                          />
                          <button
                            type="button"
                            onClick={() => toggleShowKey(provider.id)}
                            className="absolute right-3 top-1/2 -translate-y-1/2"
                          >
                            {showApiKey[provider.id] ? (
                              <EyeOff className="w-4 h-4 text-gray-500" />
                            ) : (
                              <Eye className="w-4 h-4 text-gray-500" />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Extra Key Input (if needed) */}
                      {provider.extraKey && (
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">{provider.extraKey}</label>
                          <input
                            type="text"
                            value={form.extraKey || ''}
                            onChange={(e) => setFormData(prev => ({
                              ...prev,
                              [provider.id]: { ...form, extraKey: e.target.value }
                            }))}
                            placeholder="URL o ID adicional..."
                            className="w-full px-3 py-2 bg-idm-surface border border-idm-border rounded-lg text-sm focus:outline-none focus:border-idm-primary"
                          />
                        </div>
                      )}

                      {/* Save/Cancel Buttons */}
                      <div className="flex items-center gap-2 pt-2">
                        <button
                          onClick={() => handleSave(provider.id)}
                          disabled={!form.apiKey || saveMutation.isPending}
                          className="flex items-center gap-2 px-4 py-2 bg-idm-primary text-white rounded-lg text-sm disabled:opacity-50 hover:bg-idm-primary/80 transition-colors"
                        >
                          {saveMutation.isPending ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Check className="w-4 h-4" />
                          )}
                          Guardar
                        </button>
                        <button
                          onClick={() => setEditingProvider(null)}
                          className="flex items-center gap-2 px-4 py-2 bg-idm-surface text-gray-400 rounded-lg text-sm hover:text-white transition-colors"
                        >
                          <X className="w-4 h-4" />
                          Cancelar
                        </button>
                      </div>

                      {/* Status Message */}
                      {status?.health?.last_error && (
                        <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
                          <AlertTriangle className="w-4 h-4" />
                          {status.health.last_error}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
