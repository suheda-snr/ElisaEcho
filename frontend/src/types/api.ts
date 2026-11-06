/** Response of GET /api/health (mirrors backend `HealthResponse` schema). */
export interface HealthResponse {
  status: 'ok'
  service: string
}
