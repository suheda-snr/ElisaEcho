import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import {
  analyzeThread,
  getDiscoveryEvents,
  getDiscoveryStatus,
  getDiscoveryThreads,
  getKnowledgeItem,
  getKnowledgeItems,
  getThreadMessages,
  resetDemo,
  startSimulation,
  stopSimulation,
} from '@/services/api'
import type { DiscoveryEvent, DiscoveryStatus } from '@/types/api'

// Short-interval polling keeps the UI live without WebSockets.
const FAST_POLL_MS = 1500
const IDLE_POLL_MS = 6000

export function isPipelineBusy(status: DiscoveryStatus | undefined): boolean {
  if (!status) return false
  return status.simulation.running || status.analysis.queued > 0 || status.analysis.analyzing > 0
}

export function useDiscoveryStatus() {
  return useQuery({
    queryKey: ['discovery', 'status'],
    queryFn: getDiscoveryStatus,
    refetchInterval: (query) => (isPipelineBusy(query.state.data) ? FAST_POLL_MS : IDLE_POLL_MS),
    retry: 1,
  })
}

export function useDiscoveryThreads(live: boolean) {
  return useQuery({
    queryKey: ['discovery', 'threads'],
    queryFn: getDiscoveryThreads,
    refetchInterval: live ? FAST_POLL_MS : IDLE_POLL_MS,
  })
}

export function useThreadMessages(threadId: string | null, live: boolean) {
  return useQuery({
    queryKey: ['threads', threadId, 'messages'],
    queryFn: () => getThreadMessages(threadId as string),
    enabled: threadId !== null,
    refetchInterval: live ? FAST_POLL_MS : IDLE_POLL_MS,
  })
}

export function useKnowledgeItem(id: string | null | undefined, live: boolean) {
  return useQuery({
    queryKey: ['knowledge', id],
    queryFn: () => getKnowledgeItem(id as string),
    enabled: Boolean(id),
    refetchInterval: live ? FAST_POLL_MS * 2 : false,
  })
}

export function useKnowledgeItems(live: boolean) {
  return useQuery({
    queryKey: ['knowledge', 'list'],
    queryFn: getKnowledgeItems,
    refetchInterval: live ? FAST_POLL_MS * 2 : IDLE_POLL_MS,
  })
}

/** Accumulates pipeline events incrementally (only new events are fetched). */
export function useDiscoveryEvents(live: boolean, maxEvents = 60) {
  const [events, setEvents] = useState<DiscoveryEvent[]>([])
  const lastId = useRef(0)

  const query = useQuery({
    queryKey: ['discovery', 'events'],
    queryFn: () => getDiscoveryEvents(lastId.current),
    refetchInterval: live ? FAST_POLL_MS : IDLE_POLL_MS,
  })

  useEffect(() => {
    const fresh = query.data
    if (!fresh || fresh.length === 0) return
    // The backend clears its log on reset; ids then restart from a lower number.
    const restarted = fresh[0].id <= lastId.current
    lastId.current = fresh[fresh.length - 1].id
    setEvents((previous) => [...(restarted ? [] : previous), ...fresh].slice(-maxEvents))
  }, [query.data, maxEvents])

  const reset = () => {
    lastId.current = 0
    setEvents([])
  }
  return { events, reset, error: query.error }
}

export function useSimulationControls(onReset?: () => void) {
  const queryClient = useQueryClient()
  const refresh = () => queryClient.invalidateQueries()

  const start = useMutation({ mutationFn: startSimulation, onSettled: refresh })
  const stop = useMutation({ mutationFn: stopSimulation, onSettled: refresh })
  const reset = useMutation({
    mutationFn: resetDemo,
    onSuccess: () => onReset?.(),
    onSettled: refresh,
  })
  const analyze = useMutation({ mutationFn: analyzeThread, onSettled: refresh })
  return { start, stop, reset, analyze }
}
