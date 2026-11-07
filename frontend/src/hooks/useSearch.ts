import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { searchKnowledge } from '@/services/api'
import type { SearchRequest } from '@/types/api'

/** Runs a search for the submitted request; identical searches are served from cache. */
export function useKnowledgeSearch(request: SearchRequest | null) {
  return useQuery({
    queryKey: ['search', request],
    queryFn: () => searchKnowledge(request as SearchRequest),
    enabled: request !== null,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
    retry: false,
  })
}
