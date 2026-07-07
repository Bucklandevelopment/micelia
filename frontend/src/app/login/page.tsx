'use client'

import { useState, FormEvent } from 'react'
import { useRouter } from 'next/navigation'
import { Zap, Eye, EyeOff } from 'lucide-react'
import { authApi } from '@/lib/api'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await authApi.login(username, password)
      router.push('/')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker flex items-center justify-center p-4">
      <div className="w-full max-w-md glass rounded-2xl p-8 border border-idm-border">
        {/* Branding */}
        <div className="flex flex-col items-center mb-8">
          <div className="p-3 rounded-xl bg-gradient-to-br from-idm-primary/20 to-idm-health/20 border border-idm-primary/30 mb-4">
            <Zap className="w-8 h-8 text-idm-primary" />
          </div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-idm-primary to-idm-health bg-clip-text text-transparent">
            MICELIA
          </h1>
          <p className="text-xs text-gray-500 mt-1">Orquestador del ecosistema UTOP.IA</p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm text-center">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="username" className="block text-sm text-gray-400 mb-1.5">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="w-full px-4 py-2.5 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-500 focus:outline-none focus:border-idm-primary/50 transition-colors"
              placeholder="Enter your username"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm text-gray-400 mb-1.5">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full px-4 py-2.5 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-500 focus:outline-none focus:border-idm-primary/50 transition-colors pr-11"
                placeholder="Enter your password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-idm-primary hover:bg-idm-primary/80 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
