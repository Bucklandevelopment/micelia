'use client'

import {
  Inbox,
  Layers,
  Zap,
  CheckCircle,
  FileText,
} from 'lucide-react'
import { clsx } from 'clsx'
import { Header } from '@/components/layout/Header'
import { QuickNoteInput } from '@/components/prompts/QuickNoteInput'
import { PromptQueue } from '@/components/prompts/PromptQueue'
import { PromptDetail } from '@/components/prompts/PromptDetail'
import { PromptStats } from '@/components/prompts/PromptStats'
import { InboxPanel } from '@/components/prompts/InboxPanel'
import { StagingPanel } from '@/components/prompts/StagingPanel'
import { ResultsPanel } from '@/components/prompts/ResultsPanel'
import { ListsPanel } from '@/components/prompts/ListsPanel'
import { usePromptUIStore, type PromptTab } from '@/stores/promptStore'
import {
  useInbox,
  useStaging,
  useActiveQueue,
  useResults,
  usePromptLists,
} from '@/hooks/usePrompts'

interface TabDef {
  id: PromptTab
  label: string
  icon: React.ReactNode
}

const tabs: TabDef[] = [
  { id: 'inbox', label: 'Inbox', icon: <Inbox className="w-4 h-4" /> },
  { id: 'staging', label: 'Staging', icon: <Layers className="w-4 h-4" /> },
  { id: 'queue', label: 'Queue', icon: <Zap className="w-4 h-4" /> },
  { id: 'results', label: 'Results', icon: <CheckCircle className="w-4 h-4" /> },
  { id: 'lists', label: 'Lists', icon: <FileText className="w-4 h-4" /> },
]

function TabBadge({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <span className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-semibold bg-idm-accent/20 text-idm-accent">
      {count > 99 ? '99+' : count}
    </span>
  )
}

function useTabCounts() {
  const { data: inboxData } = useInbox()
  const { data: stagingData } = useStaging()
  const { data: queueData } = useActiveQueue()
  const { data: resultsData } = useResults()
  const { data: listsData } = usePromptLists()

  return {
    inbox: inboxData?.total ?? inboxData?.count ?? 0,
    staging: stagingData?.total ?? stagingData?.count ?? 0,
    queue: queueData?.total ?? queueData?.count ?? 0,
    results: resultsData?.total ?? resultsData?.count ?? 0,
    lists: listsData?.count ?? 0,
  }
}

function ActivePanel({ tab }: { tab: PromptTab }) {
  switch (tab) {
    case 'inbox':
      return <InboxPanel />
    case 'staging':
      return <StagingPanel />
    case 'queue':
      return <PromptQueue />
    case 'results':
      return <ResultsPanel />
    case 'lists':
      return <ListsPanel />
  }
}

export default function PromptsPage() {
  const { activeTab, setActiveTab, showDetail, selectedPromptId, setShowDetail } =
    usePromptUIStore()

  const counts = useTabCounts()

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-6">
        {/* Stats Row */}
        <PromptStats />

        {/* Tab Navigation */}
        <div className="glass rounded-2xl border border-idm-border p-1.5">
          <div className="flex items-center gap-1">
            {tabs.map((tab) => {
              const isActive = activeTab === tab.id
              const count = counts[tab.id]

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={clsx(
                    'flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-idm-accent/20 text-idm-accent shadow-lg shadow-idm-accent/5'
                      : 'text-gray-500 hover:text-gray-300 hover:bg-idm-surface/50'
                  )}
                >
                  {tab.icon}
                  <span className="hidden sm:inline">{tab.label}</span>
                  <TabBadge count={count} />
                </button>
              )
            })}
          </div>
        </div>

        {/* Active Panel Content */}
        <div className="min-h-[400px]">
          <ActivePanel tab={activeTab} />
        </div>
      </main>

      {/* Prompt Detail Slide-over */}
      {showDetail && selectedPromptId && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setShowDetail(false)}
          />
          {/* Panel */}
          <div className="relative w-full max-w-xl bg-idm-darker border-l border-idm-border shadow-2xl overflow-y-auto">
            <PromptDetail />
          </div>
        </div>
      )}

      {/* Quick Note Input - Sticky Bottom */}
      <div className="sticky bottom-0 z-40 border-t border-idm-border bg-idm-darker/90 backdrop-blur-lg">
        <div className="container mx-auto px-4 py-3">
          <QuickNoteInput />
        </div>
      </div>
    </div>
  )
}
