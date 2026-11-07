import axios from 'axios'

import type {
  AnalysisResult,
  IntegrationEvent,
  SlackChannel,
  SlackChannelList,
  SlackStatus,
  CompleteSessionRequest,
  Guide,
  SessionSummary,
  StepRequest,
  TroubleshootingSession,
  DiscoveryEvent,
  DiscoveryStatus,
  HealthResponse,
  KnowledgeItemDetail,
  KnowledgeItemSummary,
  Message,
  Page,
  ResetResult,
  SearchRequest,
  SearchResponse,
  SimulationCommandResult,
  ThreadDiscovery,
} from '@/types/api'

/**
 * Shared Axios instance for all backend calls.
 *
 * The base URL defaults to the relative `/api` path. During development the
 * Vite dev server proxies `/api` to the FastAPI backend, so the browser never
 * needs to know the backend's host name.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10_000,
  headers: { Accept: 'application/json' },
})

/** Turns any thrown value into a short, human-readable message. */
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    // Prefer the backend's own explanation (e.g. "Gemini is not configured").
    const detail: unknown = error.response?.data?.detail
    if (typeof detail === 'string' && detail) {
      return detail
    }
    // 502/503/504 without a detail come from the dev proxy when the backend is down.
    if (status === 502 || status === 503 || status === 504) {
      return 'The API server is not reachable. Is the backend running?'
    }
    if (status) {
      return `Request failed with status ${status}`
    }
    if (error.code === 'ECONNABORTED') {
      return 'Request timed out'
    }
    return 'Network error: the API could not be reached'
  }
  return error instanceof Error ? error.message : 'Unknown error'
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health')
  return data
}

export async function getDiscoveryStatus(): Promise<DiscoveryStatus> {
  const { data } = await api.get<DiscoveryStatus>('/discovery/status')
  return data
}

export async function getDiscoveryEvents(after: number): Promise<DiscoveryEvent[]> {
  const { data } = await api.get<DiscoveryEvent[]>('/discovery/events', { params: { after } })
  return data
}

export async function getDiscoveryThreads(): Promise<Page<ThreadDiscovery>> {
  const { data } = await api.get<Page<ThreadDiscovery>>('/discovery/threads', {
    params: { limit: 50 },
  })
  return data
}

export async function getThreadMessages(threadId: string): Promise<Page<Message>> {
  const { data } = await api.get<Page<Message>>(`/threads/${threadId}/messages`, {
    params: { limit: 100 },
  })
  return data
}

export async function getKnowledgeItems(): Promise<Page<KnowledgeItemSummary>> {
  const { data } = await api.get<Page<KnowledgeItemSummary>>('/knowledge', {
    params: { limit: 50 },
  })
  return data
}

export async function getKnowledgeItem(id: string): Promise<KnowledgeItemDetail> {
  const { data } = await api.get<KnowledgeItemDetail>(`/knowledge/${id}`)
  return data
}

export async function startSimulation(): Promise<SimulationCommandResult> {
  const { data } = await api.post<SimulationCommandResult>('/simulation/start')
  return data
}

export async function stopSimulation(): Promise<SimulationCommandResult> {
  const { data } = await api.post<SimulationCommandResult>('/simulation/stop')
  return data
}

export async function resetDemo(): Promise<ResetResult> {
  const { data } = await api.post<ResetResult>('/simulation/reset')
  return data
}

/** Development-only: analyze one thread now (e.g. after a failure). */
export async function analyzeThread(threadId: string): Promise<AnalysisResult> {
  // Gemini can take a while; allow more than the default timeout.
  const { data } = await api.post<AnalysisResult>(`/threads/${threadId}/analyze`, null, {
    params: { force: true },
    timeout: 240_000, // backend worst case: 3 Gemini attempts x 60 s plus backoff
  })
  return data
}

export async function searchKnowledge(request: SearchRequest): Promise<SearchResponse> {
  // Allow time for the query embedding on a cold cache.
  const { data } = await api.post<SearchResponse>('/search', request, { timeout: 30_000 })
  return data
}

export async function generateGuide(problem: string, equipmentIdentifier?: string): Promise<Guide> {
  // Retrieval + Gemini drafting + validation can take a while.
  const { data } = await api.post<Guide>(
    '/guides/generate',
    { problem, equipment_identifier: equipmentIdentifier || null },
    { timeout: 180_000 },
  )
  return data
}

export async function startSession(guideId: string): Promise<TroubleshootingSession> {
  const { data } = await api.post<TroubleshootingSession>('/troubleshooting/sessions', {
    guide_id: guideId,
  })
  return data
}

export async function getSession(sessionId: string): Promise<TroubleshootingSession> {
  const { data } = await api.get<TroubleshootingSession>(`/troubleshooting/sessions/${sessionId}`)
  return data
}

export async function listSessions(): Promise<Page<SessionSummary>> {
  const { data } = await api.get<Page<SessionSummary>>('/troubleshooting/sessions', {
    params: { limit: 10 },
  })
  return data
}

export async function addSessionStep(
  sessionId: string,
  step: StepRequest,
): Promise<TroubleshootingSession> {
  const { data } = await api.post<TroubleshootingSession>(
    `/troubleshooting/sessions/${sessionId}/steps`,
    step,
  )
  return data
}

export async function completeSession(
  sessionId: string,
  body: CompleteSessionRequest,
): Promise<TroubleshootingSession> {
  const { data } = await api.post<TroubleshootingSession>(
    `/troubleshooting/sessions/${sessionId}/complete`,
    body,
  )
  return data
}

export async function getSlackStatus(): Promise<SlackStatus> {
  const { data } = await api.get<SlackStatus>('/integrations/slack/status')
  return data
}

export async function getSlackChannels(): Promise<SlackChannelList> {
  const { data } = await api.get<SlackChannelList>('/integrations/slack/channels')
  return data
}

export async function setSlackChannel(channelId: string, enabled: boolean): Promise<SlackChannel> {
  const { data } = await api.post<SlackChannel>('/integrations/slack/channels', {
    channel_id: channelId,
    enabled,
  })
  return data
}

export async function getSlackEvents(): Promise<IntegrationEvent[]> {
  const { data } = await api.get<IntegrationEvent[]>('/integrations/slack/events', {
    params: { limit: 30 },
  })
  return data
}
