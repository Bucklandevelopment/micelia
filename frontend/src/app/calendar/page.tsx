'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { calendarApi, promptsApi } from '@/lib/api'
import { Header } from '@/components/layout/Header'
import { Calendar, Link2, Unlink, RefreshCw, Plus, Clock, ExternalLink, CheckCircle, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'

interface CalendarEvent {
  id?: string
  summary: string
  start: string
  end: string
  description?: string
}

export default function CalendarPage() {
  const queryClient = useQueryClient()
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newEvent, setNewEvent] = useState({ summary: '', start: '', end: '', description: '' })

  // ---------- Queries ----------
  const { data: calStatus, isLoading: statusLoading } = useQuery({
    queryKey: ['calendar', 'status'],
    queryFn: calendarApi.status,
    refetchInterval: 30_000,
  })

  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ['calendar', 'events'],
    queryFn: () => calendarApi.events(),
    enabled: !!calStatus?.connected,
  })

  const { data: scheduledData, isLoading: scheduledLoading } = useQuery({
    queryKey: ['prompts', 'scheduled'],
    queryFn: () => promptsApi.list({ limit: 50 }),
  })

  // ---------- Mutations ----------
  const connectMutation = useMutation({
    mutationFn: async () => {
      const { auth_url } = await calendarApi.getAuthUrl()
      window.open(auth_url, '_blank', 'noopener,noreferrer')
    },
  })

  const syncMutation = useMutation({
    mutationFn: calendarApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: calendarApi.disconnect,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar'] })
    },
  })

  const createEventMutation = useMutation({
    mutationFn: (data: { summary: string; start: string; end: string; description?: string }) =>
      calendarApi.createEvent(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['calendar', 'events'] })
      setShowCreateForm(false)
      setNewEvent({ summary: '', start: '', end: '', description: '' })
    },
  })

  const isConnected = calStatus?.connected ?? false
  const events = (eventsData?.events ?? []) as CalendarEvent[]
  const scheduledPrompts = (scheduledData?.prompts ?? []).filter(
    (p: { scheduled_at?: string | null }) => p.scheduled_at
  )

  function handleCreateEvent(e: React.FormEvent) {
    e.preventDefault()
    if (!newEvent.summary || !newEvent.start || !newEvent.end) return
    createEventMutation.mutate({
      summary: newEvent.summary,
      start: newEvent.start,
      end: newEvent.end,
      description: newEvent.description || undefined,
    })
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-orange-500/10 border border-orange-500/30">
              <Calendar className="w-6 h-6 text-orange-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">Calendar Integration</h1>
              <p className="text-sm text-gray-500">Google Calendar sync and scheduled prompts</p>
            </div>
          </div>

          {/* Connection Status Badge */}
          <div
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium border',
              isConnected
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-gray-500/10 border-gray-500/30 text-gray-400'
            )}
          >
            <div
              className={clsx(
                'w-2 h-2 rounded-full',
                isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'
              )}
            />
            {statusLoading ? 'Checking...' : isConnected ? 'Connected' : 'Disconnected'}
          </div>
        </div>

        {/* Not Connected State */}
        {!isConnected && !statusLoading && (
          <div className="glass rounded-xl p-12 border border-idm-border text-center">
            <div className="mx-auto w-16 h-16 rounded-2xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center mb-6">
              <Calendar className="w-8 h-8 text-orange-400" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Connect Google Calendar</h2>
            <p className="text-gray-500 mb-8 max-w-md mx-auto">
              Sync your calendar events with Micelia to schedule prompts, view agenda, and automate workflows.
            </p>
            <button
              onClick={() => connectMutation.mutate()}
              disabled={connectMutation.isPending}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-orange-500 to-amber-500 text-white font-medium hover:from-orange-400 hover:to-amber-400 transition-all disabled:opacity-50"
            >
              <Link2 className="w-5 h-5" />
              {connectMutation.isPending ? 'Opening auth...' : 'Connect Google Calendar'}
            </button>
            {connectMutation.isError && (
              <p className="mt-4 text-sm text-red-400">Failed to get auth URL. Check backend connection.</p>
            )}
          </div>
        )}

        {/* Connected State */}
        {isConnected && (
          <>
            {/* Action Bar */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => syncMutation.mutate()}
                disabled={syncMutation.isPending}
                className={clsx(
                  'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-all',
                  'bg-idm-primary/10 border-idm-primary/30 text-idm-primary hover:bg-idm-primary/20',
                  syncMutation.isPending && 'opacity-50'
                )}
              >
                <RefreshCw className={clsx('w-4 h-4', syncMutation.isPending && 'animate-spin')} />
                {syncMutation.isPending ? 'Syncing...' : 'Sync Now'}
              </button>

              <button
                onClick={() => setShowCreateForm(!showCreateForm)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border bg-orange-500/10 border-orange-500/30 text-orange-400 hover:bg-orange-500/20 transition-all"
              >
                <Plus className="w-4 h-4" />
                Create Event
              </button>

              <div className="flex-1" />

              {calStatus?.last_sync && (
                <span className="text-xs text-gray-600">
                  Last sync: {new Date(calStatus.last_sync).toLocaleString()}
                </span>
              )}

              <button
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-all"
              >
                <Unlink className="w-4 h-4" />
                Disconnect
              </button>
            </div>

            {/* Sync Success/Error Feedback */}
            {syncMutation.isSuccess && (
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-sm text-emerald-400">
                <CheckCircle className="w-4 h-4" />
                Synced {syncMutation.data?.synced ?? 0} events
              </div>
            )}
            {syncMutation.isError && (
              <div className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-sm text-red-400">
                <AlertCircle className="w-4 h-4" />
                Sync failed. Please try again.
              </div>
            )}

            {/* Create Event Form */}
            {showCreateForm && (
              <div className="glass rounded-xl p-6 border border-orange-500/30">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Plus className="w-5 h-5 text-orange-400" />
                  New Calendar Event
                </h3>
                <form onSubmit={handleCreateEvent} className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Summary</label>
                    <input
                      type="text"
                      value={newEvent.summary}
                      onChange={(e) => setNewEvent({ ...newEvent, summary: e.target.value })}
                      placeholder="Event title..."
                      className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-orange-500/50 focus:outline-none transition-colors"
                      required
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Start</label>
                      <input
                        type="datetime-local"
                        value={newEvent.start}
                        onChange={(e) => setNewEvent({ ...newEvent, start: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white focus:border-orange-500/50 focus:outline-none transition-colors [color-scheme:dark]"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">End</label>
                      <input
                        type="datetime-local"
                        value={newEvent.end}
                        onChange={(e) => setNewEvent({ ...newEvent, end: e.target.value })}
                        className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white focus:border-orange-500/50 focus:outline-none transition-colors [color-scheme:dark]"
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Description</label>
                    <textarea
                      value={newEvent.description}
                      onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
                      placeholder="Optional event description..."
                      rows={3}
                      className="w-full px-4 py-2 rounded-lg bg-idm-surface border border-idm-border text-white placeholder-gray-600 focus:border-orange-500/50 focus:outline-none transition-colors resize-none"
                    />
                  </div>
                  <div className="flex items-center gap-3 pt-2">
                    <button
                      type="submit"
                      disabled={createEventMutation.isPending}
                      className="px-6 py-2 rounded-lg bg-gradient-to-r from-orange-500 to-amber-500 text-white font-medium hover:from-orange-400 hover:to-amber-400 transition-all disabled:opacity-50"
                    >
                      {createEventMutation.isPending ? 'Creating...' : 'Create Event'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowCreateForm(false)}
                      className="px-6 py-2 rounded-lg border border-idm-border text-gray-400 hover:text-white hover:border-gray-500 transition-all"
                    >
                      Cancel
                    </button>
                  </div>
                  {createEventMutation.isError && (
                    <p className="text-sm text-red-400">Failed to create event.</p>
                  )}
                </form>
              </div>
            )}

            {/* Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Today's Events */}
              <div className="glass rounded-xl p-6 border border-idm-border">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Calendar className="w-5 h-5 text-orange-400" />
                  Today&apos;s Events
                  {events.length > 0 && (
                    <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/30">
                      {events.length}
                    </span>
                  )}
                </h3>

                {eventsLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-16 rounded-lg bg-idm-surface animate-pulse" />
                    ))}
                  </div>
                ) : events.length === 0 ? (
                  <p className="text-gray-500 text-sm text-center py-8">No events today.</p>
                ) : (
                  <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                    {events.map((event, idx) => (
                      <div
                        key={event.id ?? idx}
                        className="p-4 rounded-lg bg-idm-surface/50 border border-idm-border/50 hover:border-orange-500/30 transition-colors group"
                      >
                        <h4 className="text-sm font-medium text-white group-hover:text-orange-400 transition-colors">
                          {event.summary}
                        </h4>
                        <div className="flex items-center gap-2 mt-1.5 text-xs text-gray-500">
                          <Clock className="w-3 h-3" />
                          <span>
                            {formatTime(event.start)} - {formatTime(event.end)}
                          </span>
                        </div>
                        {event.description && (
                          <p className="text-xs text-gray-600 mt-2 line-clamp-2">{event.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Scheduled Prompts */}
              <div className="glass rounded-xl p-6 border border-idm-border">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Clock className="w-5 h-5 text-idm-primary" />
                  Scheduled Prompts
                  {scheduledPrompts.length > 0 && (
                    <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-idm-primary/10 text-idm-primary border border-idm-primary/30">
                      {scheduledPrompts.length}
                    </span>
                  )}
                </h3>

                {scheduledLoading ? (
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-16 rounded-lg bg-idm-surface animate-pulse" />
                    ))}
                  </div>
                ) : scheduledPrompts.length === 0 ? (
                  <p className="text-gray-500 text-sm text-center py-8">No scheduled prompts.</p>
                ) : (
                  <div className="space-y-3 max-h-[400px] overflow-y-auto pr-1">
                    {scheduledPrompts.map((prompt: { prompt_id: string; content: string; scheduled_at?: string | null; category?: string }) => (
                      <div
                        key={prompt.prompt_id}
                        className="p-4 rounded-lg bg-idm-surface/50 border border-idm-border/50 hover:border-idm-primary/30 transition-colors"
                      >
                        <p className="text-sm text-gray-300 truncate">{prompt.content}</p>
                        <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {prompt.scheduled_at
                              ? new Date(prompt.scheduled_at).toLocaleString()
                              : '--'}
                          </span>
                          {prompt.category && (
                            <span className="px-1.5 py-0.5 rounded bg-idm-surface text-gray-500 border border-idm-border">
                              {prompt.category}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}
