import axios from 'axios'

import type { HealthResponse } from '@/types/api'

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
    // 502/503/504 come from the dev proxy when the backend itself is down.
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
