'use client'

import { useEffect, useState } from 'react'
import { Zap, Settings, RefreshCw, ExternalLink, Globe, Calendar, Cpu, Wand2, LogOut } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { tunnelApi, authApi } from '@/lib/api'

function TunnelIndicator() {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    const check = async () => {
      try {
        const status = await tunnelApi.status()
        setUrl(status.connected ? status.public_url : null)
      } catch { setUrl(null) }
    }
    check()
    const id = setInterval(check, 15000)
    return () => clearInterval(id)
  }, [])

  if (!url) return null

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-emerald-400 bg-emerald-500/10 rounded-full border border-emerald-500/30 hover:border-emerald-400/50 transition-all"
    >
      <Globe className="w-3 h-3 animate-pulse" />
      <span className="hidden lg:inline">Public</span>
    </a>
  )
}

export function Header() {
  const router = useRouter()

  const handleLogout = () => {
    authApi.logout()
    router.push('/login')
  }

  return (
    <header className="border-b border-idm-border bg-idm-surface/50 backdrop-blur-lg sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-gradient-to-br from-idm-primary/20 to-idm-health/20 border border-idm-primary/30">
              <Zap className="w-6 h-6 text-idm-primary" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-idm-primary to-idm-health bg-clip-text text-transparent">
                MICELIA
              </h1>
              <p className="text-xs text-gray-500">Sistema de Longevidad v1.0</p>
            </div>
            <TunnelIndicator />
          </div>

          {/* Navigation */}
          <nav className="hidden md:flex items-center gap-6">
            <Link href="/" className="text-sm text-gray-400 hover:text-white transition-colors">
              Dashboard
            </Link>
            <Link href="/prompts" className="text-sm text-gray-400 hover:text-idm-primary transition-colors">
              Prompts
            </Link>
            <Link href="/monitor" className="text-sm text-gray-400 hover:text-yellow-400 transition-colors">
              Monitor
            </Link>
            <Link href="/servicios" className="text-sm text-gray-400 hover:text-idm-health transition-colors">
              Servicios
            </Link>
            <Link href="/prompts/lists" className="text-sm text-gray-400 hover:text-purple-400 transition-colors">
              Lists
            </Link>
            <Link href="/skills" className="text-sm text-gray-400 hover:text-cyan-400 transition-colors">
              Skills
            </Link>
            <Link href="/calendar" className="text-sm text-gray-400 hover:text-orange-400 transition-colors">
              Calendar
            </Link>
            <Link href="/agents" className="text-sm text-gray-400 hover:text-pink-400 transition-colors">
              Agents
            </Link>
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* External Links */}
            <div className="hidden sm:flex items-center gap-2">
              <a
                href="http://localhost:3000"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-idm-surface rounded-lg border border-idm-border hover:border-idm-primary/50 transition-all"
              >
                <span>Grafana</span>
                <ExternalLink className="w-3 h-3" />
              </a>
              <a
                href="http://localhost:9090"
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-idm-surface rounded-lg border border-idm-border hover:border-idm-primary/50 transition-all"
              >
                <span>Prometheus</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            {/* Refresh */}
            <button className="p-2 rounded-lg bg-idm-surface border border-idm-border hover:border-idm-primary/50 transition-all">
              <RefreshCw className="w-4 h-4 text-gray-400 hover:text-white" />
            </button>

            {/* Settings */}
            <Link
              href="/settings"
              className="p-2 rounded-lg bg-idm-surface border border-idm-border hover:border-idm-primary/50 transition-all"
            >
              <Settings className="w-4 h-4 text-gray-400 hover:text-white" />
            </Link>

            {/* Logout */}
            <button
              onClick={handleLogout}
              className="p-2 rounded-lg bg-idm-surface border border-idm-border hover:border-red-500/50 transition-all"
              title="Log out"
            >
              <LogOut className="w-4 h-4 text-gray-400 hover:text-red-400" />
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
