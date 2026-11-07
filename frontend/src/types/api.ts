/** Types mirroring the backend Pydantic schemas. */

/** Response of GET /api/health. */
export interface HealthResponse {
  status: 'ok'
  service: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export type ProcessingStatus = 'pending' | 'processing' | 'processed' | 'failed'
export type DetectionStatus = 'detected' | 'incomplete' | 'rejected' | 'accepted'
export type ResolutionStatus = 'unknown' | 'suggested' | 'confirmed_in_conversation'
export type ApprovalStatus = 'unreviewed' | 'approved' | 'rejected'
export type EvidenceType =
  | 'problem_report'
  | 'attempted_fix'
  | 'suggested_solution'
  | 'confirmed_resolution'
  | 'applicability_condition'

export interface DiscoveryMetrics {
  messages_processed: number
  threads_total: number
  threads_analyzed: number
  threads_pending: number
  threads_failed: number
  candidates_detected: number
  conversations_ignored: number
  knowledge_items: number
  confirmed_resolutions: number
  unverified_suggestions: number
}

export interface SimulationStatus {
  running: boolean
  started_at: string | null
  finished_at: string | null
  delivered: number
  skipped_duplicates: number
  total: number
  message_interval_seconds: number
  last_error: string | null
}

export interface DiscoveryStatus {
  simulation: SimulationStatus
  analysis: {
    gemini_configured: boolean
    model: string
    queued: number
    analyzing: number
    debounce_seconds: number
    paused_until: string | null
    pause_reason: string | null
  }
  metrics: DiscoveryMetrics | null
  metrics_error: string | null
  development_controls: boolean
}

export interface DiscoveryEvent {
  id: number
  at: string
  kind: string
  level: 'info' | 'success' | 'warning' | 'error'
  message: string
  thread_id: string | null
  thread_title: string | null
}

export interface CandidateSummary {
  id: string
  classification: string
  detection_status: DetectionStatus
  title: string
  summary: string | null
  confidence: number | null
  model_name: string | null
  analyzed_at: string | null
  analyzed_message_count: number
  flags: string[]
  knowledge_item_id: string | null
  resolution_status: ResolutionStatus | null
  approval_status: ApprovalStatus | null
}

export interface ThreadDiscovery {
  id: string
  title: string | null
  external_thread_id: string
  processing_status: ProcessingStatus
  message_count: number
  last_message_at: string | null
  candidate: CandidateSummary | null
}

export interface Message {
  id: string
  thread_id: string
  external_message_id: string
  author_external_id: string
  author_display_name: string | null
  content: string
  sent_at: string
  edited_at: string | null
  deleted_at: string | null
  source_url: string | null
  created_at: string
}

export interface AttemptedAction {
  action: string
  outcome: 'successful' | 'unsuccessful' | 'partially_successful' | 'not_attempted' | 'unknown'
  message_ids: string[]
}

export interface KnowledgeItemSummary {
  id: string
  title: string
  problem_description: string
  resolution: string | null
  resolution_status: ResolutionStatus
  approval_status: ApprovalStatus
  created_at: string
  updated_at: string
}

export interface KnowledgeItemDetail extends KnowledgeItemSummary {
  candidate_id: string | null
  symptoms: string[]
  root_cause: string | null
  attempted_actions: AttemptedAction[]
  applicability_conditions: string[]
  evidence: {
    id: string
    evidence_type: EvidenceType
    explanation: string | null
    message: Message
  }[]
  equipment: { id: string; equipment_identifier: string }[]
  incidents: { id: string; incident_number: string; title: string }[]
  discovery: {
    thread_id: string
    classification: string
    detection_status: string
    model_name: string | null
    model_confidence: number | null
    analyzed_at: string | null
    missing_information: string[]
    validation_flags: string[]
  } | null
}

export interface SimulationCommandResult {
  changed: boolean
  simulation: SimulationStatus
}

export interface ResetResult {
  threads: number
  messages: number
  candidates: number
  knowledge_items: number
}

export interface AnalysisResult {
  thread_id: string
  status: 'analyzed' | 'unchanged' | 'empty' | 'failed' | 'not_configured' | 'deferred'
  classification: string | null
  knowledge_item_id: string | null
  resolution_status: ResolutionStatus | null
  error: string | null
}

export interface SearchFilters {
  equipment_identifier?: string | null
  incident_number?: string | null
  approval_status?: ApprovalStatus | null
  resolution_status?: ResolutionStatus | null
}

export interface SearchRequest {
  query: string
  limit?: number
  filters?: SearchFilters
}

export interface EvidenceReference {
  message_id: string
  evidence_type: EvidenceType
  explanation: string | null
  author: string
  sent_at: string
  excerpt: string | null
  deleted_at_source: boolean
  source_name: string | null
  source_type: 'slack' | 'teams' | 'simulated' | null
  thread_id: string
  thread_title: string | null
  source_url: string | null
}

export interface SearchRanking {
  score: number
  matched_by: ('semantic' | 'keyword' | 'identifier')[]
  semantic_rank: number | null
  semantic_similarity: number | null
  keyword_rank: number | null
  keyword_score: number | null
  identifier_rank: number | null
  matched_identifiers: string[]
}

export interface SearchResult {
  id: string
  title: string
  problem_description: string
  symptoms: string[]
  root_cause: string | null
  resolution: string | null
  resolution_status: ResolutionStatus
  approval_status: ApprovalStatus
  attempted_actions: AttemptedAction[]
  applicability_conditions: string[]
  missing_information: string[]
  equipment_identifiers: string[]
  incident_numbers: string[]
  evidence_status: 'supported' | 'missing'
  evidence: EvidenceReference[]
  ranking: SearchRanking
  updated_at: string
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  retrieval: {
    semantic: 'used' | 'no_embeddings' | 'unavailable' | 'not_configured'
    semantic_detail: string | null
    keyword: 'used'
    identifiers: string[]
    embedding_model: string | null
  }
  access_note: string
}

// ---- guided troubleshooting --------------------------------------------------------------

export type GuideNodeType =
  'start' | 'question' | 'diagnostic' | 'recommendation' | 'resolution' | 'escalation'
export type SupportLevel =
  'approved' | 'confirmed_in_conversation' | 'suggested' | 'conflicting' | 'none'

export interface GuideNodeEvidence {
  message_id: string
  knowledge_item_id: string
  evidence_type: EvidenceType
  author: string
  sent_at: string
  excerpt: string | null
  deleted_at_source: boolean
  source_name: string | null
  source_type: 'slack' | 'teams' | 'simulated' | null
  thread_title: string | null
  source_url: string | null
}

export interface GuideNode {
  id: string
  key: string
  node_type: GuideNodeType
  title: string
  description: string | null
  question: string | null
  expected_answers: string[]
  applicability_conditions: string[]
  knowledge_item_ids: string[]
  approval_status: ApprovalStatus | null
  support_level: SupportLevel
  requires_manual_verification: boolean
  conflict_note: string | null
  evidence: GuideNodeEvidence[]
}

export interface GuideEdge {
  id: string
  source_node_id: string
  target_node_id: string
  answer_label: string
  condition: string | null
}

export interface GuideKnowledgeRef {
  id: string
  title: string
  problem_description: string
  resolution: string | null
  resolution_status: ResolutionStatus
  approval_status: ApprovalStatus
  applicability_conditions: string[]
  missing_information: string[]
  equipment_identifiers: string[]
  incident_numbers: string[]
  conversation: string | null
  source_name: string | null
}

export interface Guide {
  id: string
  title: string
  problem_description: string
  equipment_identifier: string | null
  status: 'ready' | 'insufficient_evidence'
  status_reason: string | null
  summary: string | null
  model_name: string | null
  created_at: string
  start_node_id: string | null
  nodes: GuideNode[]
  edges: GuideEdge[]
  knowledge: GuideKnowledgeRef[]
  conflicts: string[]
  uncertainties: string[]
  validation_notes: string[]
  safety_notice: string
}

export type SessionStatus = 'in_progress' | 'resolved' | 'unresolved'

export interface SessionStep {
  id: string
  sequence: number
  step_type: 'answer' | 'observation' | 'back' | 'complete'
  node_id: string | null
  answer_label: string | null
  target_node_id: string | null
  observation: string | null
  action_taken: string | null
  superseded: boolean
  created_at: string
}

export interface TroubleshootingSession {
  id: string
  guide_id: string
  status: SessionStatus
  current_node_id: string | null
  active_path: string[]
  outcome_summary: string | null
  action_taken: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  steps: SessionStep[]
  note: string
  guide: Guide
}

export interface SessionSummary {
  id: string
  guide_id: string
  guide_title: string
  problem_description: string
  status: SessionStatus
  updated_at: string
}

export type StepRequest =
  | { type: 'answer'; answer_label: string; observation?: string; action_taken?: string }
  | { type: 'observation'; observation?: string; action_taken?: string }
  | { type: 'back'; to_node_id?: string }

export interface CompleteSessionRequest {
  outcome: 'resolved' | 'unresolved'
  summary: string
  action_taken?: string
  observation?: string
}
