'use client'

import { useState, useCallback } from 'react'
import { Save, Eye, EyeOff, Loader2, Check } from 'lucide-react'
import { clsx } from 'clsx'
import { promptsApi } from '@/lib/api'
import type { PromptList } from '@/types/api'

interface PromptListEditorProps {
  list: PromptList
  onClose?: () => void
}

export function PromptListEditor({ list, onClose }: PromptListEditorProps) {
  const [content, setContent] = useState(list.content_md)
  const [showPreview, setShowPreview] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const isDirty = content !== list.content_md

  const handleSave = useCallback(async () => {
    if (!isDirty || isSaving) return
    setIsSaving(true)
    setSaved(false)
    try {
      await promptsApi.updateList(list.slug, { content_md: content })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setIsSaving(false)
    }
  }, [content, isDirty, isSaving, list.slug])

  return (
    <div className="glass rounded-xl border border-idm-border overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-idm-border bg-idm-surface/50">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-white">{list.name}</h3>
          {isDirty && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-energy-conserving/15 text-energy-conserving">
              Modified
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Preview toggle */}
          <button
            type="button"
            onClick={() => setShowPreview(!showPreview)}
            className={clsx(
              'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors',
              showPreview
                ? 'bg-idm-primary/15 text-idm-primary border border-idm-primary/30'
                : 'bg-idm-surface text-gray-400 border border-idm-border hover:text-gray-300'
            )}
          >
            {showPreview ? (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                Edit
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                Preview
              </>
            )}
          </button>

          {/* Save button */}
          <button
            type="button"
            onClick={handleSave}
            disabled={!isDirty || isSaving}
            className={clsx(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200',
              isDirty && !isSaving
                ? 'bg-idm-primary text-idm-darker hover:bg-idm-primary/90 shadow-lg shadow-idm-primary/20'
                : saved
                  ? 'bg-energy-abundant/20 text-energy-abundant border border-energy-abundant/30'
                  : 'bg-idm-surface text-gray-500 border border-idm-border cursor-not-allowed'
            )}
          >
            {isSaving ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : saved ? (
              <Check className="w-3.5 h-3.5" />
            ) : (
              <Save className="w-3.5 h-3.5" />
            )}
            {isSaving ? 'Saving...' : saved ? 'Saved' : 'Save'}
          </button>
        </div>
      </div>

      {/* Editor / Preview area */}
      {showPreview ? (
        <div className="p-4 min-h-[300px] max-h-[500px] overflow-y-auto">
          <div className="prose prose-invert prose-sm max-w-none">
            {content.split('\n').map((line, i) => {
              // Basic markdown rendering
              if (line.startsWith('### ')) {
                return (
                  <h3 key={i} className="text-sm font-semibold text-white mt-3 mb-1">
                    {line.slice(4)}
                  </h3>
                )
              }
              if (line.startsWith('## ')) {
                return (
                  <h2 key={i} className="text-base font-semibold text-white mt-4 mb-1">
                    {line.slice(3)}
                  </h2>
                )
              }
              if (line.startsWith('# ')) {
                return (
                  <h1 key={i} className="text-lg font-bold text-white mt-4 mb-2">
                    {line.slice(2)}
                  </h1>
                )
              }
              if (line.startsWith('- ') || line.startsWith('* ')) {
                return (
                  <li key={i} className="text-sm text-gray-300 ml-4 list-disc">
                    {line.slice(2)}
                  </li>
                )
              }
              if (line.trim() === '') {
                return <br key={i} />
              }
              return (
                <p key={i} className="text-sm text-gray-300 my-1">
                  {line}
                </p>
              )
            })}
          </div>
        </div>
      ) : (
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          spellCheck={false}
          className={clsx(
            'w-full min-h-[300px] max-h-[500px] p-4 bg-transparent resize-y',
            'font-mono text-sm text-gray-200 leading-relaxed',
            'focus:outline-none',
            'placeholder-gray-600'
          )}
          placeholder="Write your prompt list content in Markdown..."
        />
      )}
    </div>
  )
}
