'use client'

import { Header } from '@/components/layout/Header'
import { useServicesHealth } from '@/hooks/useServicesHealth'
import { serviceCatalog, type RegistryServiceStatus } from '@/lib/services'
import { ExternalLink, CheckCircle, XCircle, HelpCircle, Boxes } from 'lucide-react'

type Estado = 'healthy' | 'unhealthy' | 'unknown'

function estadoDe(
  registryKey: string | null,
  services: Record<string, RegistryServiceStatus> | undefined,
  isLoading: boolean,
): { estado: Estado; version: string | null; error: string | null } {
  // Sin sonda en el registry (codking/auto-mat-ion): no hay salud viva.
  if (registryKey === null) return { estado: 'unknown', version: null, error: null }
  if (isLoading || !services) return { estado: 'unknown', version: null, error: null }
  const s = services[registryKey]
  if (!s) return { estado: 'unknown', version: null, error: null }
  return {
    estado: s.healthy ? 'healthy' : 'unhealthy',
    version: s.version,
    error: s.error,
  }
}

const BADGE: Record<Estado, { cls: string; label: string; Icon: typeof CheckCircle }> = {
  healthy: {
    cls: 'text-green-400 bg-green-500/10 border-green-500/30',
    label: 'Healthy',
    Icon: CheckCircle,
  },
  unhealthy: {
    cls: 'text-red-400 bg-red-500/10 border-red-500/30',
    label: 'Unhealthy',
    Icon: XCircle,
  },
  unknown: {
    cls: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
    label: 'Sin sonda',
    Icon: HelpCircle,
  },
}

export default function ServiciosPage() {
  const { data: services, isLoading } = useServicesHealth()

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Boxes className="w-6 h-6 text-idm-primary" />
            Servicios del ecosistema
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Acceso directo a cada frontend de dominio. La salud viene del registry del
            gateway (<code className="text-gray-400">/api/v1/health/services</code>) y se
            refresca cada 15s. Arranca los servicios con{' '}
            <code className="text-gray-400">scripts/run-ecosystem.sh start</code>.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {serviceCatalog.map((svc) => {
            const { estado, version, error } = estadoDe(svc.registryKey, services, isLoading)
            const badge = BADGE[estado]
            const BadgeIcon = badge.Icon
            return (
              <div
                key={svc.id}
                className="glass rounded-xl p-5 border border-idm-border flex flex-col gap-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{svc.nombre}</h3>
                    {version && (
                      <span className="text-xs text-gray-500">v{version}</span>
                    )}
                  </div>
                  <span
                    className={`flex items-center gap-1 px-2 py-1 text-xs rounded-full border ${badge.cls}`}
                    title={error ?? undefined}
                  >
                    <BadgeIcon className="w-3 h-3" />
                    {badge.label}
                  </span>
                </div>

                <p className="text-sm text-gray-400 flex-1">{svc.descripcion}</p>

                <a
                  href={svc.frontendUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => {
                    // SSO hand-off (C119): para dominios que aceptan el token de Micelia,
                    // adjuntamos el access token en el FRAGMENTO de la URL (no viaja al
                    // servidor ni se loguea) para que el usuario llegue ya logueado.
                    if (!svc.sso) return
                    const token =
                      typeof window !== 'undefined'
                        ? localStorage.getItem('vital_access_token')
                        : null
                    if (!token) return
                    e.preventDefault()
                    window.open(
                      `${svc.frontendUrl}#sso_token=${encodeURIComponent(token)}`,
                      '_blank',
                      'noopener,noreferrer'
                    )
                  }}
                  className="flex items-center justify-center gap-1.5 px-3 py-2 text-sm text-gray-300 hover:text-white bg-idm-surface rounded-lg border border-idm-border hover:border-idm-primary/50 transition-all"
                >
                  <span>{svc.enlaceLabel}</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
                <span className="text-xs text-gray-600 truncate" title={svc.frontendUrl}>
                  {svc.frontendUrl}
                </span>
              </div>
            )
          })}
        </div>
      </main>
    </div>
  )
}
