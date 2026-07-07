'use client'

import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { ProviderSettings } from '@/components/settings/ProviderSettings'
import { SystemSettings } from '@/components/settings/SystemSettings'
import { QuotaMonitor } from '@/components/settings/QuotaMonitor'
import { Settings, Cloud, Gauge, Shield } from 'lucide-react'
import { clsx } from 'clsx'

type SettingsTab = 'providers' | 'quotas' | 'system'

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('providers')

  const tabs = [
    { id: 'providers' as const, label: 'Proveedores Cloud', icon: Cloud },
    { id: 'quotas' as const, label: 'Cuotas & Uso', icon: Gauge },
    { id: 'system' as const, label: 'Sistema', icon: Shield },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6">
        {/* Page Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="p-3 rounded-xl bg-idm-primary/10 border border-idm-primary/30">
            <Settings className="w-6 h-6 text-idm-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Configuracion</h1>
            <p className="text-sm text-gray-500">Gestiona proveedores cloud, API keys y cuotas del sistema Frangels</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 border-b border-idm-border pb-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all',
                activeTab === tab.id
                  ? 'bg-idm-primary/20 text-idm-primary border border-idm-primary/30'
                  : 'text-gray-400 hover:text-white hover:bg-idm-surface'
              )}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="space-y-6">
          {activeTab === 'providers' && <ProviderSettings />}
          {activeTab === 'quotas' && <QuotaMonitor />}
          {activeTab === 'system' && <SystemSettings />}
        </div>
      </main>
    </div>
  )
}
