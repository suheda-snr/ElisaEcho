import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  addSessionStep,
  completeSession,
  generateGuide,
  getSession,
  listSessions,
  startSession,
} from '@/services/api'
import type {
  CompleteSessionRequest,
  Guide,
  StepRequest,
  TroubleshootingSession,
} from '@/types/api'

const sessionKey = (id: string | null) => ['troubleshooting', 'session', id]

export function useSession(sessionId: string | null) {
  return useQuery({
    queryKey: sessionKey(sessionId),
    queryFn: () => getSession(sessionId as string),
    enabled: sessionId !== null,
    retry: false,
  })
}

export function useRecentSessions() {
  return useQuery({ queryKey: ['troubleshooting', 'sessions'], queryFn: listSessions })
}

/** Generate a guide and, when it has steps, immediately start a session for it. */
export function useGenerateGuide(
  onResult: (guide: Guide, session: TroubleshootingSession | null) => void,
) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: async ({ problem, equipment }: { problem: string; equipment?: string }) => {
      const guide = await generateGuide(problem, equipment)
      const session = guide.status === 'ready' ? await startSession(guide.id) : null
      return { guide, session }
    },
    onSuccess: ({ guide, session }) => {
      if (session) client.setQueryData(sessionKey(session.id), session)
      onResult(guide, session)
      void client.invalidateQueries({ queryKey: ['troubleshooting', 'sessions'] })
    },
  })
}

export function useSessionActions(sessionId: string | null) {
  const client = useQueryClient()
  const store = (session: TroubleshootingSession) => {
    client.setQueryData(sessionKey(session.id), session)
    void client.invalidateQueries({ queryKey: ['troubleshooting', 'sessions'] })
  }
  const step = useMutation({
    mutationFn: (body: StepRequest) => addSessionStep(sessionId as string, body),
    onSuccess: store,
  })
  const complete = useMutation({
    mutationFn: (body: CompleteSessionRequest) => completeSession(sessionId as string, body),
    onSuccess: store,
  })
  return { step, complete }
}
