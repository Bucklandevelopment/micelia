'use client'

import { useEffect, useRef, useState, useCallback, KeyboardEvent } from 'react'
import { Send, Loader2, Hash, X } from 'lucide-react'
import { clsx } from 'clsx'
import { useCreateNote } from '@/hooks/usePrompts'
import { usePromptUIStore } from '@/stores/promptStore'

const LOCAL_STORAGE_KEY = 'idm-quick-note-draft'

function extractTags(text: string): string[] {
  const matches = text.match(/#[\w-]+/g)
  if (!matches) return []
  return Array.from(new Set(matches.map((t) => t.slice(1))))
}

export function QuickNoteInput() {
  const { quickNoteText, setQuickNoteText, isNoteSubmitting, setNoteSubmitting } =
    usePromptUIStore()

  const [isFocused, setIsFocused] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const createNote = useCreateNote()

  const tags = extractTags(quickNoteText)

  // Load draft from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(LOCAL_STORAGE_KEY)
    if (saved && !quickNoteText) {
      setQuickNoteText(saved)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-save to localStorage on text change
  useEffect(() => {
    localStorage.setItem(LOCAL_STORAGE_KEY, quickNoteText)
  }, [quickNoteText])

  // Focus textarea when expanded
  useEffect(() => {
    if (isFocused && textareaRef.current) {
      textareaRef.current.focus()
    }
  }, [isFocused])

  const handleSubmit = useCallback(async () => {
    const text = quickNoteText.trim()
    if (!text || isNoteSubmitting) return

    setNoteSubmitting(true)
    try {
      await createNote.mutateAsync({ text, tags: tags.length > 0 ? tags : undefined })
      setQuickNoteText('')
      localStorage.removeItem(LOCAL_STORAGE_KEY)
      setIsFocused(false)
    } finally {
      setNoteSubmitting(false)
    }
  }, [quickNoteText, isNoteSubmitting, createNote, tags, setNoteSubmitting, setQuickNoteText])

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const removeTag = (tag: string) => {
    const updated = quickNoteText.replace(new RegExp(`#${tag}\\b`, 'g'), '').replace(/\s{2,}/g, ' ').trim()
    setQuickNoteText(updated)
  }

  return (
    <div className="sticky bottom-0 z-30 w-full">
      <div className="glass border-t border-idm-border px-4 py-3">
        {/* Tag chips */}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {tags.map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-idm-primary/15 text-idm-primary border border-idm-primary/20"
              >
                <Hash className="w-3 h-3" />
                {tag}
                <button
                  type="button"
                  onClick={() => removeTag(tag)}
                  className="hover:text-white transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Input area */}
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            {isFocused ? (
              <textarea
                ref={textareaRef}
                value={quickNoteText}
                onChange={(e) => setQuickNoteText(e.target.value)}
                onBlur={() => {
                  if (!quickNoteText.trim()) setIsFocused(false)
                }}
                onKeyDown={handleKeyDown}
                placeholder="Write a quick note... use #tags"
                rows={3}
                className={clsx(
                  'w-full bg-idm-surface border border-idm-border rounded-lg px-4 py-3',
                  'text-sm text-white placeholder-gray-500 resize-none',
                  'focus:outline-none focus:border-idm-primary/50 focus:ring-1 focus:ring-idm-primary/20',
                  'transition-all duration-200'
                )}
              />
            ) : (
              <input
                ref={inputRef}
                type="text"
                value={quickNoteText}
                onChange={(e) => setQuickNoteText(e.target.value)}
                onFocus={() => setIsFocused(true)}
                onKeyDown={handleKeyDown}
                placeholder="Write a quick note... use #tags"
                className={clsx(
                  'w-full bg-idm-surface border border-idm-border rounded-lg px-4 py-3',
                  'text-sm text-white placeholder-gray-500',
                  'focus:outline-none focus:border-idm-primary/50 focus:ring-1 focus:ring-idm-primary/20',
                  'transition-all duration-200'
                )}
              />
            )}
          </div>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={!quickNoteText.trim() || isNoteSubmitting}
            className={clsx(
              'p-3 rounded-lg transition-all duration-200',
              'flex items-center justify-center',
              quickNoteText.trim() && !isNoteSubmitting
                ? 'bg-idm-primary text-idm-darker hover:bg-idm-primary/90 shadow-lg shadow-idm-primary/20'
                : 'bg-idm-surface text-gray-500 cursor-not-allowed'
            )}
          >
            {isNoteSubmitting ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>

        <p className="text-xs text-gray-600 mt-1.5 px-1">
          Enter to send, Shift+Enter for newline
        </p>
      </div>
    </div>
  )
}
