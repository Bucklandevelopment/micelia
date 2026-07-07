'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { skillsApi, mcpApi } from '@/lib/api'
import type { Skill, MCPServer } from '@/lib/api'
import { Header } from '@/components/layout/Header'
import { Wand2, Plus, Power, Trash2, Play, Server, Code2, X, ChevronRight, Zap, PowerOff } from 'lucide-react'
import { clsx } from 'clsx'

type ActiveTab = 'skills' | 'mcp'

export default function SkillsPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<ActiveTab>('skills')

  const tabs = [
    { id: 'skills' as const, label: 'Skills', icon: Wand2 },
    { id: 'mcp' as const, label: 'MCP Servers', icon: Server },
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-cyan-500/10 border border-cyan-500/30">
            <Wand2 className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Skills Manager</h1>
            <p className="text-sm text-gray-500">Create, test, and manage skills and MCP servers</p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-idm-border pb-4">
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
        {activeTab === 'skills' && <SkillsTab />}
        {activeTab === 'mcp' && <MCPServersTab />}
      </main>
    </div>
  )
}

// ===================== Skills Tab =====================

function SkillsTab() {
  const queryClient = useQueryClient()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingSkill, setEditingSkill] = useState<Skill | null>(null)
  const [testingSlug, setTestingSlug] = useState<string | null>(null)
  const [testInput, setTestInput] = useState('')

  const { data, isLoading, error } = useQuery({
    queryKey: ['skills'],
    queryFn: skillsApi.list,
  })

  const toggleMutation = useMutation({
    mutationFn: (slug: string) => skillsApi.toggle(slug),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['skills'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (slug: string) => skillsApi.delete(slug),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['skills'] }),
  })

  const testMutation = useMutation({
    mutationFn: ({ slug, prompt }: { slug: string; prompt: string }) =>
      skillsApi.test(slug, prompt),
  })

  const skills = data?.skills ?? []

  function handleTestSubmit(slug: string) {
    if (!testInput.trim()) return
    testMutation.mutate({ slug, prompt: testInput.trim() })
  }

  if (error) {
    return (
      <div className="glass rounded-xl p-8 border border-red-500/30 text-center">
        <p className="text-red-400">Failed to load skills. Is the backend running?</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-500">{skills.length} skill{skills.length !== 1 ? 's' : ''}</span>
        <button
          onClick={() => { setShowCreateForm(true); setEditingSkill(null) }}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-medium hover:from-cyan-400 hover:to-blue-400 transition-all"
        >
          <Plus className="w-4 h-4" />
          Create Skill
        </button>
      </div>

      {/* Create/Edit Form */}
      {(showCreateForm || editingSkill) && (
        <SkillForm
          skill={editingSkill}
          onClose={() => { setShowCreateForm(false); setEditingSkill(null) }}
        />
      )}

      {/* Skills Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-44 rounded-xl bg-idm-surface animate-pulse" />
          ))}
        </div>
      ) : skills.length === 0 ? (
        <div className="glass rounded-xl p-12 border border-idm-border text-center">
          <Wand2 className="w-10 h-10 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500">No skills created yet. Create your first skill above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {skills.map((skill) => (
            <div
              key={skill.skill_id}
              className="glass rounded-xl p-5 border border-idm-border hover:border-cyan-500/30 transition-all group"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-white group-hover:text-cyan-400 transition-colors truncate">
                    {skill.name}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{skill.description}</p>
                </div>
                {/* Toggle */}
                <button
                  onClick={() => toggleMutation.mutate(skill.slug)}
                  disabled={toggleMutation.isPending}
                  className={clsx(
                    'relative w-10 h-5 rounded-full transition-colors shrink-0 ml-3',
                    skill.is_active ? 'bg-cyan-500' : 'bg-gray-600'
                  )}
                >
                  <span
                    className={clsx(
                      'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform',
                      skill.is_active ? 'left-5' : 'left-0.5'
                    )}
                  />
                </button>
              </div>

              {/* Trigger Pattern */}
              <div className="mb-3">
                <span className="text-xs text-gray-600">Trigger:</span>
                <code className="ml-2 text-xs px-2 py-0.5 rounded bg-idm-surface border border-idm-border text-cyan-400 font-mono">
                  {skill.trigger_pattern}
                </code>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between pt-3 border-t border-idm-border/50">
                <span className="text-xs text-gray-600">
                  Used {skill.usage_count} time{skill.usage_count !== 1 ? 's' : ''}
                </span>
                <div className="flex items-center gap-2">
                  {/* Test Button */}
                  <button
                    onClick={() => setTestingSlug(testingSlug === skill.slug ? null : skill.slug)}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-cyan-400 hover:bg-cyan-500/10 transition-all"
                    title="Test skill"
                  >
                    <Play className="w-3.5 h-3.5" />
                  </button>
                  {/* Edit Button */}
                  <button
                    onClick={() => { setEditingSkill(skill); setShowCreateForm(false) }}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-idm-surface transition-all"
                    title="Edit skill"
                  >
                    <Code2 className="w-3.5 h-3.5" />
                  </button>
                  {/* Delete Button */}
                  <button
                    onClick={() => deleteMutation.mutate(skill.slug)}
                    disabled={deleteMutation.isPending}
                    className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                    title="Delete skill"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Inline Test Input */}
              {testingSlug === skill.slug && (
                <div className="mt-3 pt-3 border-t border-idm-border/50 space-y-2">
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={testInput}
                      onChange={(e) => setTestInput(e.target.value)}
                      placeholder="Enter test prompt..."
                      className="flex-1 px-3 py-1.5 rounded-lg bg-idm-surface border border-idm-border text-sm text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none"
                      onKeyDown={(e) => e.key === 'Enter' && handleTestSubmit(skill.slug)}
                    />
                    <button
                      onClick={() => handleTestSubmit(skill.slug)}
                      disabled={testMutation.isPending || !testInput.trim()}
                      className="px-3 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-400 text-sm border border-cyan-500/30 hover:bg-cyan-500/30 disabled:opacity-50 transition-all"
                    >
                      {testMutation.isPending ? '...' : 'Run'}
                    </button>
                  </div>
                  {testMutation.isSuccess && (
                    <pre className="text-xs text-gray-300 bg-idm-surface rounded-lg p-3 border border-idm-border overflow-auto max-h-32">
                      {testMutation.data?.result ?? 'No output'}
                    </pre>
                  )}
                  {testMutation.isError && (
                    <p className="text-xs text-red-400">Test failed.</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ===================== Skill Form =====================

function SkillForm({ skill, onClose }: { skill: Skill | null; onClose: () => void }) {
  const queryClient = useQueryClient()
  const isEditing = !!skill

  const [form, setForm] = useState({
    name: skill?.name ?? '',
    description: skill?.description ?? '',
    trigger_pattern: skill?.trigger_pattern ?? '',
    prompt_template: skill?.prompt_template ?? '',
  })

  const createMutation = useMutation({
    mutationFn: (data: typeof form) => skillsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      onClose()
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: typeof form) => skillsApi.update(skill!.slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['skills'] })
      onClose()
    },
  })

  const mutation = isEditing ? updateMutation : createMutation
  const isPending = mutation.isPending

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name || !form.trigger_pattern || !form.prompt_template) return
    mutation.mutate(form)
  }

  return (
    <div className="glass rounded-xl p-6 border border-cyan-500/30">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Wand2 className="w-5 h-5 text-cyan-400" />
          {isEditing ? 'Edit Skill' : 'Create Skill'}
        </h3>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-idm-surface transition-all">
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="My Skill"
              className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none transition-colors"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Trigger Pattern (regex)</label>
            <input
              type="text"
              value={form.trigger_pattern}
              onChange={(e) => setForm({ ...form, trigger_pattern: e.target.value })}
              placeholder="^summarize\s+"
              className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none transition-colors font-mono text-sm"
              required
            />
          </div>
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Description</label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="What does this skill do?"
            className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none transition-colors"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Prompt Template</label>
          <textarea
            value={form.prompt_template}
            onChange={(e) => setForm({ ...form, prompt_template: e.target.value })}
            placeholder="You are a helpful assistant. {{input}}"
            rows={5}
            className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-cyan-500/50 focus:outline-none transition-colors resize-none font-mono text-sm"
            required
          />
        </div>
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={isPending}
            className="px-6 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-500 text-white font-medium hover:from-cyan-400 hover:to-blue-400 transition-all disabled:opacity-50"
          >
            {isPending ? 'Saving...' : isEditing ? 'Update Skill' : 'Create Skill'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-2 rounded-lg border border-idm-border text-gray-400 hover:text-white hover:border-gray-500 transition-all"
          >
            Cancel
          </button>
        </div>
        {mutation.isError && (
          <p className="text-sm text-red-400">Failed to {isEditing ? 'update' : 'create'} skill.</p>
        )}
      </form>
    </div>
  )
}

// ===================== MCP Servers Tab =====================

function MCPServersTab() {
  const queryClient = useQueryClient()
  const [showGenerateForm, setShowGenerateForm] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['mcp', 'servers'],
    queryFn: mcpApi.servers,
  })

  const startMutation = useMutation({
    mutationFn: (id: string) => mcpApi.start(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp', 'servers'] }),
  })

  const stopMutation = useMutation({
    mutationFn: (id: string) => mcpApi.stop(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp', 'servers'] }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => mcpApi.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['mcp', 'servers'] }),
  })

  const servers = data?.servers ?? []

  if (error) {
    return (
      <div className="glass rounded-xl p-8 border border-red-500/30 text-center">
        <p className="text-red-400">Failed to load MCP servers.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-500">{servers.length} server{servers.length !== 1 ? 's' : ''}</span>
        <button
          onClick={() => setShowGenerateForm(!showGenerateForm)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-medium hover:from-purple-400 hover:to-pink-400 transition-all"
        >
          <Plus className="w-4 h-4" />
          Generate Server
        </button>
      </div>

      {/* Generate Form */}
      {showGenerateForm && (
        <MCPGenerateForm onClose={() => setShowGenerateForm(false)} />
      )}

      {/* Servers Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-40 rounded-xl bg-idm-surface animate-pulse" />
          ))}
        </div>
      ) : servers.length === 0 ? (
        <div className="glass rounded-xl p-12 border border-idm-border text-center">
          <Server className="w-10 h-10 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-500">No MCP servers yet. Generate one above.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {servers.map((server) => (
            <div
              key={server.server_id}
              className="glass rounded-xl p-5 border border-idm-border hover:border-purple-500/30 transition-all group"
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-semibold text-white group-hover:text-purple-400 transition-colors truncate">
                    {server.name}
                  </h3>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{server.description}</p>
                </div>
                {/* Status Badge */}
                <span
                  className={clsx(
                    'px-2 py-0.5 rounded-full text-xs font-medium border shrink-0 ml-3',
                    server.status === 'running'
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-gray-500/10 border-gray-500/30 text-gray-400'
                  )}
                >
                  {server.status}
                </span>
              </div>

              {/* Language + Tools */}
              <div className="flex items-center gap-3 mb-3">
                <span
                  className={clsx(
                    'px-2 py-0.5 rounded text-xs font-medium border',
                    server.language === 'python'
                      ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                      : 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                  )}
                >
                  {server.language === 'python' ? 'Python' : 'TypeScript'}
                </span>
                <span className="text-xs text-gray-600">
                  {server.tools.length} tool{server.tools.length !== 1 ? 's' : ''}
                </span>
              </div>

              {/* Tools Preview */}
              {server.tools.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {server.tools.slice(0, 4).map((tool) => (
                    <span
                      key={tool.name}
                      className="px-2 py-0.5 rounded bg-idm-surface border border-idm-border text-xs text-gray-400"
                    >
                      {tool.name}
                    </span>
                  ))}
                  {server.tools.length > 4 && (
                    <span className="px-2 py-0.5 rounded bg-idm-surface border border-idm-border text-xs text-gray-600">
                      +{server.tools.length - 4}
                    </span>
                  )}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2 pt-3 border-t border-idm-border/50">
                {server.status === 'stopped' ? (
                  <button
                    onClick={() => startMutation.mutate(server.server_id)}
                    disabled={startMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-50 transition-all"
                  >
                    <Power className="w-3 h-3" />
                    Start
                  </button>
                ) : (
                  <button
                    onClick={() => stopMutation.mutate(server.server_id)}
                    disabled={stopMutation.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 hover:bg-yellow-500/20 disabled:opacity-50 transition-all"
                  >
                    <PowerOff className="w-3 h-3" />
                    Stop
                  </button>
                )}
                <div className="flex-1" />
                <button
                  onClick={() => deleteMutation.mutate(server.server_id)}
                  disabled={deleteMutation.isPending}
                  className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-all"
                  title="Delete server"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ===================== MCP Generate Form =====================

function MCPGenerateForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()

  const [form, setForm] = useState({
    name: '',
    description: '',
    language: 'python' as 'python' | 'typescript',
    tools: [{ name: '', description: '' }],
  })

  const generateMutation = useMutation({
    mutationFn: (data: { name: string; description: string; tools: { name: string; description: string }[]; language: string }) =>
      mcpApi.generate(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['mcp', 'servers'] })
      onClose()
    },
  })

  function addTool() {
    setForm({ ...form, tools: [...form.tools, { name: '', description: '' }] })
  }

  function removeTool(index: number) {
    if (form.tools.length <= 1) return
    setForm({ ...form, tools: form.tools.filter((_, i) => i !== index) })
  }

  function updateTool(index: number, field: 'name' | 'description', value: string) {
    const updated = [...form.tools]
    updated[index] = { ...updated[index], [field]: value }
    setForm({ ...form, tools: updated })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const validTools = form.tools.filter((t) => t.name.trim())
    if (!form.name || validTools.length === 0) return
    generateMutation.mutate({ ...form, tools: validTools })
  }

  return (
    <div className="glass rounded-xl p-6 border border-purple-500/30">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Server className="w-5 h-5 text-purple-400" />
          Generate MCP Server
        </h3>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-idm-surface transition-all">
          <X className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2">
            <label className="block text-sm text-gray-400 mb-1">Server Name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="my-mcp-server"
              className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Language</label>
            <select
              value={form.language}
              onChange={(e) => setForm({ ...form, language: e.target.value as 'python' | 'typescript' })}
              className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white focus:border-purple-500/50 focus:outline-none transition-colors"
            >
              <option value="python">Python</option>
              <option value="typescript">TypeScript</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-400 mb-1">Description</label>
          <input
            type="text"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="What does this server do?"
            className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
          />
        </div>

        {/* Tools List */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm text-gray-400">Tools</label>
            <button
              type="button"
              onClick={addTool}
              className="flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300 transition-colors"
            >
              <Plus className="w-3 h-3" />
              Add Tool
            </button>
          </div>
          <div className="space-y-2">
            {form.tools.map((tool, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="text"
                  value={tool.name}
                  onChange={(e) => updateTool(idx, 'name', e.target.value)}
                  placeholder="tool_name"
                  className="flex-1 px-3 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-purple-500/50 focus:outline-none text-sm font-mono transition-colors"
                />
                <input
                  type="text"
                  value={tool.description}
                  onChange={(e) => updateTool(idx, 'description', e.target.value)}
                  placeholder="Tool description"
                  className="flex-[2] px-3 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-purple-500/50 focus:outline-none text-sm transition-colors"
                />
                <button
                  type="button"
                  onClick={() => removeTool(idx)}
                  disabled={form.tools.length <= 1}
                  className="p-2 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-30 transition-all"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={generateMutation.isPending}
            className="px-6 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium hover:from-purple-400 hover:to-pink-400 transition-all disabled:opacity-50"
          >
            {generateMutation.isPending ? 'Generating...' : 'Generate Server'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-6 py-2 rounded-lg border border-idm-border text-gray-400 hover:text-white hover:border-gray-500 transition-all"
          >
            Cancel
          </button>
        </div>
        {generateMutation.isError && (
          <p className="text-sm text-red-400">Failed to generate MCP server.</p>
        )}
      </form>
    </div>
  )
}
