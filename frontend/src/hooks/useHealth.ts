import { useQuery } from '@tanstack/react-query'

import { api, getHealth } from '@/services/api'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30_000,
    retry: 1,
  })
}

export interface DatabaseHealth {
  status: 'ok' | 'unavailable'
  database: 'connected' | 'not_configured' | 'misconfigured' | 'unreachable'
  pgvector: boolean | null
  detail: string | null
}

/** GET /api/health/db answers 503 with a JSON body when unavailable; both are valid states. */
export function useDatabaseHealth() {
  return useQuery({
    queryKey: ['health', 'db'],
    queryFn: async () => {
      const { data } = await api.get<DatabaseHealth>('/health/db', { validateStatus: () => true })
      return data
    },
    refetchInterval: 60_000,
  })
}
