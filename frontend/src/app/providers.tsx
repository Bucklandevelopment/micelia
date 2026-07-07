'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { MSWProvider } from '@/mocks/MSWProvider'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30 seconds
            refetchInterval: 30 * 1000, // Refresh every 30s
            retry: 2,
          },
        },
      })
  )

  return (
    <MSWProvider>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </MSWProvider>
  )
}
