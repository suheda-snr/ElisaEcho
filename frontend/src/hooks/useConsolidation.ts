import { useQuery } from '@tanstack/react-query'

import {
  getGroupRelationships,
  getKnowledgeGroup,
  getKnowledgeGroups,
  getRelatedKnowledge,
} from '@/services/api'

const POLL_MS = 15_000 // consolidation runs in the background after discovery

export function useRelatedKnowledge(id: string | null | undefined) {
  return useQuery({
    queryKey: ['knowledge', id, 'related'],
    queryFn: () => getRelatedKnowledge(id as string),
    enabled: Boolean(id),
    refetchInterval: POLL_MS,
  })
}

export function useKnowledgeGroups() {
  return useQuery({
    queryKey: ['knowledge-groups'],
    queryFn: getKnowledgeGroups,
    refetchInterval: POLL_MS,
  })
}

export function useKnowledgeGroup(id: string | null | undefined) {
  return useQuery({
    queryKey: ['knowledge-groups', id],
    queryFn: () => getKnowledgeGroup(id as string),
    enabled: Boolean(id),
    refetchInterval: POLL_MS,
  })
}

export function useGroupRelationships(id: string | null | undefined) {
  return useQuery({
    queryKey: ['knowledge-groups', id, 'relationships'],
    queryFn: () => getGroupRelationships(id as string),
    enabled: Boolean(id),
    refetchInterval: POLL_MS,
  })
}
