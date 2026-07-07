'use client'

import { Calendar } from 'lucide-react'

interface CalendarEvent {
  summary: string
  start: string
  end: string
}

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso.slice(11, 16)
  }
}

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    const today = new Date()
    if (d.toDateString() === today.toDateString()) return 'Hoy'
    const tomorrow = new Date(today)
    tomorrow.setDate(today.getDate() + 1)
    if (d.toDateString() === tomorrow.toDateString()) return 'Manana'
    return d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric' })
  } catch {
    return ''
  }
}

export function CalendarUpcoming({ events }: { events?: CalendarEvent[] }) {
  const items = events ?? []

  return (
    <div className="glass rounded-xl p-5 border border-idm-border">
      <h3 className="text-sm font-medium text-gray-400 mb-3 flex items-center gap-1.5">
        <Calendar className="w-4 h-4 text-orange-400" />
        Calendar
      </h3>

      {items.length === 0 ? (
        <p className="text-xs text-gray-600 text-center py-4">No upcoming events</p>
      ) : (
        <div className="space-y-2">
          {items.map((event, i) => (
            <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-idm-surface/50">
              <div className="text-center shrink-0 w-10">
                <div className="text-[10px] text-orange-400">{formatDate(event.start)}</div>
                <div className="text-xs text-gray-300 font-mono">{formatTime(event.start)}</div>
              </div>
              <span className="text-xs text-gray-300 truncate">{event.summary}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
