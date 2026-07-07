'use client'

import { Header } from '@/components/layout/Header'
import { EnergyStatus } from '@/components/panel-idm/EnergyStatus'
import { SystemStatus } from '@/components/panel-idm/SystemStatus'
import { PromptActivityCard, PromptActivitySkeleton } from '@/components/mission-control/PromptActivityCard'
import { BudgetWidget, BudgetSkeleton } from '@/components/mission-control/BudgetWidget'
import { QueuePreview, QueueSkeleton } from '@/components/mission-control/QueuePreview'
import { RecentResults, ResultsSkeleton } from '@/components/mission-control/RecentResults'
import { AgentStatusCard } from '@/components/mission-control/AgentStatusCard'
import { CalendarUpcoming } from '@/components/mission-control/CalendarUpcoming'
import { QuickActions } from '@/components/mission-control/QuickActions'
import { useDashboardSummary } from '@/hooks/useDashboard'
import { Zap } from 'lucide-react'

export default function MissionControl() {
  const { data, isLoading, error } = useDashboardSummary()

  return (
    <div className="min-h-screen bg-gradient-to-br from-idm-darker via-idm-dark to-idm-darker">
      <Header />

      <main className="container mx-auto px-4 py-6 space-y-5">
        {/* Mission Control Title */}
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-idm-primary" />
          <h2 className="text-lg font-semibold text-white">Mission Control</h2>
          {error && (
            <span className="text-xs text-red-400 ml-2">API unavailable</span>
          )}
        </div>

        {/* Row 1: Activity + Budget */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2">
            {isLoading ? <PromptActivitySkeleton /> : <PromptActivityCard data={data?.activity} />}
          </div>
          <div>
            {isLoading ? <BudgetSkeleton /> : <BudgetWidget data={data?.budget} />}
          </div>
        </div>

        {/* Quick Actions */}
        <QuickActions />

        {/* Row 2: Queue + Results */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {isLoading ? <QueueSkeleton /> : <QueuePreview items={data?.queue_preview} />}
          {isLoading ? <ResultsSkeleton /> : <RecentResults items={data?.recent_results} />}
        </div>

        {/* Row 3: Agents + Calendar + System */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <AgentStatusCard data={data?.agents} />
          <CalendarUpcoming events={data?.calendar_upcoming} />
          <SystemStatus />
        </div>

        {/* Row 4: Energy (demoted) */}
        <EnergyStatus />
      </main>
    </div>
  )
}
