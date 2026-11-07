import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  correctFeedback,
  getFeedbackSummary,
  getKnowledgeFeedback,
  getSessionFeedback,
  submitFeedback,
} from '@/services/api'
import type { FeedbackCreate, FeedbackInput } from '@/types/api'

/**
 * Edit tokens prove "I submitted this" (there are no user accounts). They live only in this
 * browser; losing one just means the feedback can no longer be corrected from here.
 */
const tokenKey = (id: string) => `elisa-echo:feedback-token:${id}`

export function feedbackToken(id: string): string | null {
  try {
    return window.localStorage.getItem(tokenKey(id))
  } catch {
    return null
  }
}

function rememberToken(id: string, token: string) {
  try {
    window.localStorage.setItem(tokenKey(id), token)
  } catch {
    // storage unavailable (private mode): correction from this browser will not be possible
  }
}

export function useSessionFeedback(sessionId: string | null) {
  return useQuery({
    queryKey: ['feedback', 'session', sessionId],
    queryFn: () => getSessionFeedback(sessionId as string),
    enabled: sessionId !== null,
  })
}

export function useKnowledgeFeedback(knowledgeId: string | null) {
  return useQuery({
    queryKey: ['feedback', 'knowledge', knowledgeId],
    queryFn: () => getKnowledgeFeedback(knowledgeId as string),
    enabled: knowledgeId !== null,
  })
}

export function useFeedbackSummary(knowledgeId: string | null) {
  return useQuery({
    queryKey: ['feedback', 'summary', knowledgeId],
    queryFn: () => getFeedbackSummary(knowledgeId as string),
    enabled: knowledgeId !== null,
  })
}

export function useSaveFeedback() {
  const client = useQueryClient()
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['feedback'] })
    void client.invalidateQueries({ queryKey: ['search'] })
  }
  const submit = useMutation({
    mutationFn: (body: FeedbackCreate) => submitFeedback(body),
    onSuccess: (saved) => {
      if (saved.edit_token) rememberToken(saved.id, saved.edit_token)
      refresh()
    },
  })
  const correct = useMutation({
    mutationFn: ({ id, body }: { id: string; body: FeedbackInput }) =>
      correctFeedback(id, body, feedbackToken(id)),
    onSuccess: refresh,
  })
  return { submit, correct }
}
