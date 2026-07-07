'use client'

import { BarChart3, Activity, ExternalLink, Database, Cpu, Gauge } from 'lucide-react'

interface MetricLink {
  name: string
  url: string
  icon: React.ReactNode
  description: string
}

const metricLinks: MetricLink[] = [
  {
    name: 'Grafana',
    url: 'http://localhost:3000',
    icon: <BarChart3 className="w-5 h-5" />,
    description: 'Dashboards y visualizacion de metricas'
  },
  {
    name: 'Prometheus',
    url: 'http://localhost:9090',
    icon: <Activity className="w-5 h-5" />,
    description: 'Queries y alertas de metricas'
  },
  {
    name: 'Redis Insight',
    url: 'http://localhost:8001',
    icon: <Database className="w-5 h-5" />,
    description: 'Monitor de cache y pub/sub'
  },
  {
    name: 'API Docs',
    url: 'http://localhost:8888/docs',
    icon: <Cpu className="w-5 h-5" />,
    description: 'Swagger UI de Micelia'
  },
]

export function MetricsLinks() {
  return (
    <div className="glass rounded-xl p-6 border border-idm-border h-full">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className="p-2 rounded-lg bg-idm-primary/10">
          <Gauge className="w-5 h-5 text-idm-primary" />
        </div>
        <div>
          <h2 className="text-lg font-semibold">Metricas</h2>
          <p className="text-xs text-gray-500">Herramientas de monitoreo</p>
        </div>
      </div>

      {/* Links Grid */}
      <div className="space-y-3">
        {metricLinks.map((link, idx) => (
          <a
            key={idx}
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-3 p-3 rounded-lg bg-idm-surface/50 hover:bg-idm-surface border border-transparent hover:border-idm-primary/30 transition-all group"
          >
            <div className="p-2 rounded-lg bg-idm-primary/10 text-idm-primary group-hover:bg-idm-primary/20 transition-colors">
              {link.icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{link.name}</span>
                <ExternalLink className="w-3 h-3 text-gray-500 group-hover:text-idm-primary transition-colors" />
              </div>
              <p className="text-xs text-gray-500 truncate">{link.description}</p>
            </div>
          </a>
        ))}
      </div>

      {/* Quick Stats */}
      <div className="mt-4 pt-4 border-t border-idm-border">
        <div className="grid grid-cols-2 gap-3">
          <div className="text-center p-3 bg-idm-surface/50 rounded-lg">
            <div className="text-xl font-bold text-idm-health">99.9%</div>
            <div className="text-xs text-gray-500">Uptime</div>
          </div>
          <div className="text-center p-3 bg-idm-surface/50 rounded-lg">
            <div className="text-xl font-bold text-idm-primary">12ms</div>
            <div className="text-xs text-gray-500">Latencia P99</div>
          </div>
        </div>
      </div>
    </div>
  )
}
