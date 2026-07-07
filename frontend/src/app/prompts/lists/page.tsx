'use client'

import { useState } from 'react'
import { Header } from '@/components/layout/Header'
import { PromptListCard } from '@/components/prompts/PromptListCard'
import { PromptListEditor } from '@/components/prompts/PromptListEditor'
import { usePromptLists } from '@/hooks/usePrompts'
import { Plus, List } from 'lucide-react'
import type { PromptList } from '@/types/api'

export default function PromptListsPage() {
  const { data, isLoading } = usePromptLists()
  const [selectedList, setSelectedList] = useState<PromptList | null>(null)

  const lists = data?.lists ?? []

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Page Title + Actions */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-purple-500/10 border border-purple-500/20">
              <List className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Prompt Lists</h2>
              <p className="text-sm text-gray-500">
                {lists.length} list{lists.length !== 1 ? 's' : ''} created
              </p>
            </div>
          </div>
          <button
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-500 rounded-lg transition-colors border border-purple-500/30"
            onClick={() =>
              setSelectedList({
                list_id: '',
                name: '',
                slug: '',
                description: null,
                category: 'general',
                content_md: '',
                is_active: true,
                created_at: new Date().toISOString(),
                updated_at: null,
                metadata: {},
              })
            }
          >
            <Plus className="w-4 h-4" />
            New List
          </button>
        </div>

        {/* Lists Grid */}
        {isLoading ? (
          <div className="glass rounded-xl p-12 border border-idm-border text-center">
            <div className="animate-pulse text-gray-500">Loading lists...</div>
          </div>
        ) : lists.length === 0 ? (
          <div className="glass rounded-xl p-12 border border-idm-border text-center">
            <List className="w-10 h-10 text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400 text-sm">No prompt lists yet.</p>
            <p className="text-gray-600 text-xs mt-1">
              Create your first list to organize prompts by topic or workflow.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {lists.map((list) => (
              <PromptListCard
                key={list.list_id}
                list={list}
                isSelected={selectedList?.list_id === list.list_id}
                onClick={() => setSelectedList(list)}
              />
            ))}
          </div>
        )}

        {/* Selected List Editor */}
        {selectedList && (
          <div className="glass rounded-xl p-6 border border-idm-border">
            <PromptListEditor
              list={selectedList}
              onClose={() => setSelectedList(null)}
            />
          </div>
        )}
      </main>
    </div>
  )
}
