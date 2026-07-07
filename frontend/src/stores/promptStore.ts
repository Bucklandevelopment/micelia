import { create } from 'zustand'

export type PromptTab = 'inbox' | 'staging' | 'queue' | 'results' | 'lists'

interface PromptUIState {
  activeTab: PromptTab
  selectedPromptId: string | null
  filterStatus: string | null
  filterCategory: string | null
  filterTags: string[]
  quickNoteText: string
  isNoteSubmitting: boolean
  showDetail: boolean

  setActiveTab: (tab: PromptTab) => void
  setSelectedPrompt: (id: string | null) => void
  setFilterStatus: (status: string | null) => void
  setFilterCategory: (category: string | null) => void
  setFilterTags: (tags: string[]) => void
  setQuickNoteText: (text: string) => void
  setNoteSubmitting: (v: boolean) => void
  setShowDetail: (v: boolean) => void
  clearFilters: () => void
}

export const usePromptUIStore = create<PromptUIState>((set) => ({
  activeTab: 'inbox',
  selectedPromptId: null,
  filterStatus: null,
  filterCategory: null,
  filterTags: [],
  quickNoteText: '',
  isNoteSubmitting: false,
  showDetail: false,

  setActiveTab: (tab) => set({ activeTab: tab }),
  setSelectedPrompt: (id) => set({ selectedPromptId: id, showDetail: !!id }),
  setFilterStatus: (status) => set({ filterStatus: status }),
  setFilterCategory: (category) => set({ filterCategory: category }),
  setFilterTags: (tags) => set({ filterTags: tags }),
  setQuickNoteText: (text) => set({ quickNoteText: text }),
  setNoteSubmitting: (v) => set({ isNoteSubmitting: v }),
  setShowDetail: (v) => set({ showDetail: v }),
  clearFilters: () => set({ filterStatus: null, filterCategory: null, filterTags: [] }),
}))
