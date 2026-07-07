'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { agentsApi, promptsApi } from '@/lib/api'
import type { AgentCrew, AgentRun } from '@/lib/api'
import { Header } from '@/components/layout/Header'
import { Users, Play, GitBranch, Clock, CheckCircle, XCircle, ArrowRight, Plus, ChevronDown, ChevronUp, X, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'

const AVAILABLE_AGENTS = ['Planner', 'Executor', 'Reviewer', 'Critic', 'Patcher'] as const

export default function AgentsPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-pink-500/10 border border-pink-500/30">
            <Users className="w-6 h-6 text-pink-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Multi-Agent Orchestration</h1>
            <p className="text-sm text-gray-500">Workflows, crews, and execution runs</p>
          </div>
        </div>

        {/* Three Sections */}
        <WorkflowsSection />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <CrewsSection />
          <RunsSection />
        </div>
      </main>
    </div>
  )
}

// ===================== Workflows Section =====================

function WorkflowsSection() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['agents', 'workflows'],
    queryFn: agentsApi.workflows,
  })

  const { data: runsData } = useQuery({
    queryKey: ['agents', 'runs'],
    queryFn: agentsApi.runs,
    refetchInterval: 5_000,
  })

  const workflows = data?.workflows ?? []
  const activeRuns = (runsData?.runs ?? []).filter((r) => r.status === 'running')

  if (error) {
    return (
      <div className="glass rounded-xl p-8 border border-red-500/30 text-center">
        <p className="text-red-400">Failed to load workflows. Is the backend running?</p>
      </div>
    )
  }

  // Parse a workflow string like "plan > execute > review" into steps
  function parseSteps(workflow: string): string[] {
    return workflow.split(/\s*>\s*/).map((s) => s.trim()).filter(Boolean)
  }

  // Find active run for a workflow to highlight the current step
  function getActiveStepIndex(workflow: string): number {
    const run = activeRuns.find((r) => r.workflow === workflow)
    if (!run) return -1
    const currentIdx = run.steps.findIndex((s) => s.status === 'running')
    return currentIdx >= 0 ? currentIdx : -1
  }

  return (
    <div className="glass rounded-xl p-6 border border-idm-border">
      <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <GitBranch className="w-5 h-5 text-pink-400" />
        Workflows
      </h2>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-idm-surface animate-pulse" />
          ))}
        </div>
      ) : workflows.length === 0 ? (
        <p className="text-gray-500 text-sm text-center py-8">No workflows available.</p>
      ) : (
        <div className="space-y-4">
          {workflows.map((workflow) => {
            const steps = parseSteps(workflow)
            const activeIdx = getActiveStepIndex(workflow)

            return (
              <div
                key={workflow}
                className="p-4 rounded-lg bg-idm-surface/50 border border-idm-border/50 hover:border-pink-500/30 transition-colors"
              >
                <div className="flex items-center gap-2 mb-3">
                  <GitBranch className="w-4 h-4 text-pink-400" />
                  <span className="text-sm font-medium text-white">{workflow}</span>
                  {activeIdx >= 0 && (
                    <span className="ml-auto px-2 py-0.5 rounded-full text-xs bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 animate-pulse">
                      Running
                    </span>
                  )}
                </div>

                {/* Pipeline Visualization */}
                <div className="flex items-center gap-2 flex-wrap">
                  {steps.map((step, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <div
                        className={clsx(
                          'px-3 py-1.5 rounded-lg text-xs font-medium border transition-all',
                          idx === activeIdx
                            ? 'bg-yellow-500/20 border-yellow-500/50 text-yellow-300 animate-pulse'
                            : idx < activeIdx
                              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                              : 'bg-idm-surface border-idm-border text-gray-400'
                        )}
                      >
                        {step}
                      </div>
                      {idx < steps.length - 1 && (
                        <ArrowRight
                          className={clsx(
                            'w-3.5 h-3.5 shrink-0',
                            idx < activeIdx ? 'text-emerald-500' : 'text-gray-600'
                          )}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ===================== Crews Section =====================

function CrewsSection() {
  const queryClient = useQueryClient()
  const [showCreateForm, setShowCreateForm] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['agents', 'crews'],
    queryFn: agentsApi.crews,
  })

  const { data: workflowsData } = useQuery({
    queryKey: ['agents', 'workflows'],
    queryFn: agentsApi.workflows,
  })

  const crews = data?.crews ?? []
  const workflows = workflowsData?.workflows ?? []

  return (
    <div className="glass rounded-xl p-6 border border-idm-border">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Users className="w-5 h-5 text-purple-400" />
          Crews
        </h2>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-purple-500/10 border border-purple-500/30 text-purple-400 hover:bg-purple-500/20 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          Create Crew
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <CrewCreateForm
          workflows={workflows}
          onClose={() => setShowCreateForm(false)}
        />
      )}

      {/* Error State */}
      {error && (
        <p className="text-red-400 text-sm text-center py-4">Failed to load crews.</p>
      )}

      {/* Loading State */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-24 rounded-lg bg-idm-surface animate-pulse" />
          ))}
        </div>
      ) : crews.length === 0 && !error ? (
        <p className="text-gray-500 text-sm text-center py-8">No crews created yet.</p>
      ) : (
        <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
          {crews.map((crew) => (
            <div
              key={crew.crew_id}
              className="p-4 rounded-lg bg-idm-surface/50 border border-idm-border/50 hover:border-purple-500/30 transition-colors"
            >
              <h4 className="text-sm font-semibold text-white mb-2">{crew.name}</h4>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {crew.agents.map((agent) => (
                  <span
                    key={agent}
                    className="px-2 py-0.5 rounded text-xs bg-pink-500/10 border border-pink-500/30 text-pink-400"
                  >
                    {agent}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-600">
                <GitBranch className="w-3 h-3" />
                <span>{crew.workflow}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ===================== Crew Create Form =====================

function CrewCreateForm({ workflows, onClose }: { workflows: string[]; onClose: () => void }) {
  const queryClient = useQueryClient()

  const [form, setForm] = useState({
    name: '',
    agents: [] as string[],
    workflow: workflows[0] ?? '',
  })

  const createMutation = useMutation({
    mutationFn: (data: { name: string; agents: string[]; workflow: string }) =>
      agentsApi.createCrew(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents', 'crews'] })
      onClose()
    },
  })

  function toggleAgent(agent: string) {
    setForm((prev) => ({
      ...prev,
      agents: prev.agents.includes(agent)
        ? prev.agents.filter((a) => a !== agent)
        : [...prev.agents, agent],
    }))
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.name || form.agents.length === 0 || !form.workflow) return
    createMutation.mutate(form)
  }

  return (
    <div className="mb-4 p-4 rounded-lg bg-idm-surface border border-purple-500/30">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-purple-400">New Crew</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-idm-border transition-all">
          <X className="w-3.5 h-3.5 text-gray-400" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="text"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Crew name"
          className="w-full px-3 py-2 rounded-lg bg-idm-darker border border-idm-border text-sm text-white placeholder-gray-600 focus:border-purple-500/50 focus:outline-none transition-colors"
          required
        />

        {/* Agent Multi-Select */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Agents</label>
          <div className="flex flex-wrap gap-2">
            {AVAILABLE_AGENTS.map((agent) => (
              <button
                key={agent}
                type="button"
                onClick={() => toggleAgent(agent)}
                className={clsx(
                  'px-2.5 py-1 rounded text-xs font-medium border transition-all',
                  form.agents.includes(agent)
                    ? 'bg-pink-500/20 border-pink-500/50 text-pink-300'
                    : 'bg-idm-darker border-idm-border text-gray-500 hover:text-white'
                )}
              >
                {agent}
              </button>
            ))}
          </div>
        </div>

        {/* Workflow Select */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Workflow</label>
          <select
            value={form.workflow}
            onChange={(e) => setForm({ ...form, workflow: e.target.value })}
            className="w-full px-3 py-2 rounded-lg bg-idm-darker border border-idm-border text-sm text-white focus:border-purple-500/50 focus:outline-none transition-colors"
          >
            {workflows.length === 0 && <option value="">No workflows available</option>}
            {workflows.map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            type="submit"
            disabled={createMutation.isPending || form.agents.length === 0}
            className="px-4 py-1.5 rounded-lg bg-purple-500/20 text-purple-400 text-xs font-medium border border-purple-500/30 hover:bg-purple-500/30 disabled:opacity-50 transition-all"
          >
            {createMutation.isPending ? 'Creating...' : 'Create'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg border border-idm-border text-xs text-gray-400 hover:text-white transition-all"
          >
            Cancel
          </button>
        </div>
        {createMutation.isError && (
          <p className="text-xs text-red-400">Failed to create crew.</p>
        )}
      </form>
    </div>
  )
}

// ===================== Runs Section =====================

function RunsSection() {
  const queryClient = useQueryClient()
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null)
  const [showExecuteForm, setShowExecuteForm] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['agents', 'runs'],
    queryFn: agentsApi.runs,
    refetchInterval: 5_000,
  })

  const runs = data?.runs ?? []

  return (
    <div className="glass rounded-xl p-6 border border-idm-border">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Play className="w-5 h-5 text-emerald-400" />
          Runs
        </h2>
        <button
          onClick={() => setShowExecuteForm(!showExecuteForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20 transition-all"
        >
          <Play className="w-3.5 h-3.5" />
          Execute
        </button>
      </div>

      {/* Execute Form */}
      {showExecuteForm && (
        <ExecuteForm onClose={() => setShowExecuteForm(false)} />
      )}

      {/* Error State */}
      {error && (
        <p className="text-red-400 text-sm text-center py-4">Failed to load runs.</p>
      )}

      {/* Loading State */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-idm-surface animate-pulse" />
          ))}
        </div>
      ) : runs.length === 0 && !error ? (
        <p className="text-gray-500 text-sm text-center py-8">No runs yet. Execute a workflow above.</p>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
          {runs.map((run) => {
            const isExpanded = expandedRunId === run.run_id

            return (
              <div key={run.run_id} className="rounded-lg border border-idm-border/50 overflow-hidden">
                {/* Run Header */}
                <button
                  onClick={() => setExpandedRunId(isExpanded ? null : run.run_id)}
                  className="w-full flex items-center gap-3 p-3 bg-idm-surface/50 hover:bg-idm-surface/80 transition-colors text-left"
                >
                  {/* Status Icon */}
                  {run.status === 'running' && <Loader2 className="w-4 h-4 text-yellow-400 animate-spin shrink-0" />}
                  {run.status === 'completed' && <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />}
                  {run.status === 'failed' && <XCircle className="w-4 h-4 text-red-400 shrink-0" />}

                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-white font-medium truncate block">{run.workflow}</span>
                    <span className="text-xs text-gray-600">{formatRelativeTime(run.started_at)}</span>
                  </div>

                  {/* Status Badge */}
                  <span
                    className={clsx(
                      'px-2 py-0.5 rounded-full text-xs font-medium border shrink-0',
                      run.status === 'running' && 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400',
                      run.status === 'completed' && 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
                      run.status === 'failed' && 'bg-red-500/10 border-red-500/30 text-red-400'
                    )}
                  >
                    {run.status}
                  </span>

                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-gray-500 shrink-0" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-gray-500 shrink-0" />
                  )}
                </button>

                {/* Expanded Steps */}
                {isExpanded && run.steps.length > 0 && (
                  <div className="border-t border-idm-border/30 bg-idm-darker/50 p-3 space-y-2">
                    {run.steps.map((step, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-3 p-2.5 rounded-lg bg-idm-surface/30 border border-idm-border/30"
                      >
                        {/* Step Status */}
                        {step.status === 'running' && <Loader2 className="w-3.5 h-3.5 text-yellow-400 animate-spin mt-0.5 shrink-0" />}
                        {step.status === 'completed' && <CheckCircle className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" />}
                        {step.status === 'failed' && <XCircle className="w-3.5 h-3.5 text-red-400 mt-0.5 shrink-0" />}
                        {step.status !== 'running' && step.status !== 'completed' && step.status !== 'failed' && (
                          <Clock className="w-3.5 h-3.5 text-gray-500 mt-0.5 shrink-0" />
                        )}

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-white">{step.agent}</span>
                            {step.duration_ms != null && (
                              <span className="text-xs text-gray-600 flex items-center gap-0.5">
                                <Clock className="w-3 h-3" />
                                {(step.duration_ms / 1000).toFixed(1)}s
                              </span>
                            )}
                          </div>
                          {step.output && (
                            <p className="text-xs text-gray-400 mt-1 line-clamp-3 whitespace-pre-wrap">{step.output}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ===================== Execute Form =====================

function ExecuteForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()

  const [promptId, setPromptId] = useState('')
  const [selectedWorkflow, setSelectedWorkflow] = useState('')

  const { data: workflowsData } = useQuery({
    queryKey: ['agents', 'workflows'],
    queryFn: agentsApi.workflows,
  })

  const { data: promptsData } = useQuery({
    queryKey: ['prompts', 'forExecution'],
    queryFn: () => promptsApi.list({ status: 'queued', limit: 20 }),
  })

  const workflows = workflowsData?.workflows ?? []
  const prompts = promptsData?.prompts ?? []

  const executeMutation = useMutation({
    mutationFn: (data: { prompt_id: string; workflow?: string }) =>
      agentsApi.execute(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents', 'runs'] })
      onClose()
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!promptId) return
    executeMutation.mutate({
      prompt_id: promptId,
      workflow: selectedWorkflow || undefined,
    })
  }

  return (
    <div className="mb-4 p-4 rounded-lg bg-idm-surface border border-emerald-500/30">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-emerald-400">Execute Workflow</span>
        <button onClick={onClose} className="p-1 rounded hover:bg-idm-border transition-all">
          <X className="w-3.5 h-3.5 text-gray-400" />
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Prompt Select */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Prompt</label>
          <select
            value={promptId}
            onChange={(e) => setPromptId(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-idm-darker border border-idm-border text-sm text-white focus:border-emerald-500/50 focus:outline-none transition-colors"
            required
          >
            <option value="">Select a prompt...</option>
            {prompts.map((p: { prompt_id: string; content: string }) => (
              <option key={p.prompt_id} value={p.prompt_id}>
                {p.content.slice(0, 80)}{p.content.length > 80 ? '...' : ''}
              </option>
            ))}
          </select>
          {prompts.length === 0 && (
            <p className="text-xs text-gray-600 mt-1">No queued prompts. Create one in the Prompts page.</p>
          )}
        </div>

        {/* Workflow Select */}
        <div>
          <label className="block text-xs text-gray-500 mb-1.5">Workflow (optional)</label>
          <select
            value={selectedWorkflow}
            onChange={(e) => setSelectedWorkflow(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-idm-darker border border-idm-border text-sm text-white focus:border-emerald-500/50 focus:outline-none transition-colors"
          >
            <option value="">Default workflow</option>
            {workflows.map((w) => (
              <option key={w} value={w}>{w}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <button
            type="submit"
            disabled={executeMutation.isPending || !promptId}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 text-xs font-medium border border-emerald-500/30 hover:bg-emerald-500/30 disabled:opacity-50 transition-all"
          >
            <Play className="w-3 h-3" />
            {executeMutation.isPending ? 'Executing...' : 'Execute'}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg border border-idm-border text-xs text-gray-400 hover:text-white transition-all"
          >
            Cancel
          </button>
        </div>
        {executeMutation.isError && (
          <p className="text-xs text-red-400">Failed to execute workflow.</p>
        )}
      </form>
    </div>
  )
}

// ===================== Utility =====================

function formatRelativeTime(iso: string): string {
  const now = Date.now()
  const then = new Date(iso).getTime()
  const diff = now - then
  const seconds = Math.floor(diff / 1000)

  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
