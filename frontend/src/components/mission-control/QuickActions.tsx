'use client'

import Link from 'next/link'
import { PenLine, ListOrdered, Wand2, Calendar, Settings, Activity, ShieldCheck } from 'lucide-react'

const actions = [
  { href: '/prompts', icon: PenLine, label: 'Prompts', color: 'text-idm-primary' },
  { href: '/prompts/lists', icon: ListOrdered, label: 'Lists', color: 'text-purple-400' },
  { href: '/skills', icon: Wand2, label: 'Skills', color: 'text-cyan-400' },
  { href: '/calendar', icon: Calendar, label: 'Calendar', color: 'text-orange-400' },
  { href: '/monitor', icon: Activity, label: 'Monitor', color: 'text-yellow-400' },
  { href: '/audit', icon: ShieldCheck, label: 'Audit', color: 'text-amber-400' },
  { href: '/settings', icon: Settings, label: 'Settings', color: 'text-gray-400' },
]

export function QuickActions() {
  return (
    <div className="flex items-center gap-2 overflow-x-auto pb-1">
      {actions.map(({ href, icon: Icon, label, color }) => (
        <Link
          key={href}
          href={href}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-idm-surface/50 border border-idm-border/50 hover:border-idm-primary/30 transition-all shrink-0"
        >
          <Icon className={`w-3.5 h-3.5 ${color}`} />
          <span className="text-xs text-gray-300">{label}</span>
        </Link>
      ))}
    </div>
  )
}
