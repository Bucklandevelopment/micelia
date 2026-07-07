'use client'

import { ReactNode } from 'react'
import { clsx } from 'clsx'
import { ChevronRight } from 'lucide-react'

interface Feature {
  icon: ReactNode
  label: string
  value: string
}

interface PillarCardProps {
  title: string
  icon: ReactNode
  color: 'health' | 'education' | 'identity'
  description: string
  features: Feature[]
}

const colorClasses = {
  health: {
    border: 'border-idm-health/30 hover:border-idm-health/50',
    bg: 'bg-idm-health/10',
    text: 'text-idm-health',
    glow: 'hover:shadow-[0_0_30px_rgba(0,255,136,0.15)]',
  },
  education: {
    border: 'border-idm-education/30 hover:border-idm-education/50',
    bg: 'bg-idm-education/10',
    text: 'text-idm-education',
    glow: 'hover:shadow-[0_0_30px_rgba(255,215,0,0.15)]',
  },
  identity: {
    border: 'border-idm-identity/30 hover:border-idm-identity/50',
    bg: 'bg-idm-identity/10',
    text: 'text-idm-identity',
    glow: 'hover:shadow-[0_0_30px_rgba(255,107,107,0.15)]',
  },
}

export function PillarCard({ title, icon, color, description, features }: PillarCardProps) {
  const colors = colorClasses[color]

  return (
    <div className={clsx(
      'glass rounded-xl p-6 border transition-all duration-300 cursor-pointer group',
      colors.border,
      colors.glow
    )}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={clsx('p-3 rounded-xl', colors.bg, colors.text)}>
            {icon}
          </div>
          <div>
            <h3 className={clsx('text-lg font-semibold', colors.text)}>{title}</h3>
            <p className="text-xs text-gray-500">{description}</p>
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-500 group-hover:text-white transition-colors" />
      </div>

      {/* Features */}
      <div className="space-y-3">
        {features.map((feature, idx) => (
          <div
            key={idx}
            className="flex items-center justify-between py-2 px-3 bg-idm-surface/50 rounded-lg"
          >
            <div className="flex items-center gap-2">
              <span className="text-gray-400">{feature.icon}</span>
              <span className="text-sm text-gray-300">{feature.label}</span>
            </div>
            <span className={clsx('text-sm font-medium', colors.text)}>
              {feature.value}
            </span>
          </div>
        ))}
      </div>

      {/* Footer action */}
      <div className="mt-4 pt-4 border-t border-idm-border">
        <button className={clsx(
          'text-sm font-medium flex items-center gap-1 transition-colors',
          colors.text,
          'hover:opacity-80'
        )}>
          Ver detalles
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
