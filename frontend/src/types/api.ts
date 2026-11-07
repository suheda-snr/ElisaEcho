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
  knowledge_reused: number
  sessions_completed: number
  feedback_resolved: number
  feedback_not_resolved: number
  knowledge_with_conflicting_feedback: number
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
    embedding_model: string | null
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
  source_name: string | null
  source_type: 'slack' | 'teams' | 'simulated' | null
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

export type KnowledgeType = 'troubleshooting' | 'site_access'

export interface EntityLink {
  entity_type: 'equipment' | 'unit_class' | 'site' | 'event'
  label: string
  relation: 'observed_on' | 'applies_to' | 'located_at' | 'access_to' | 'triggered_by'
  source: 'conversation' | 'inventory'
}

/** Context-assertion fields: type, time validity and entity bindings. */
export interface ContextFields {
  knowledge_type: KnowledgeType
  valid_from: string | null
  /** null = still believed true */
  valid_to: string | null
  validity_note: string | null
  superseded_by: { id: string; title: string } | null
  entity_links: EntityLink[]
}

export interface KnowledgeItemSummary {
  id: string
  title: string
  problem_description: string
  resolution: string | null
  resolution_status: ResolutionStatus
  approval_status: ApprovalStatus
  knowledge_type: KnowledgeType
  valid_to: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeItemDetail extends ContextFields, KnowledgeItemSummary {
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
  /** ISO time: what was believed true then */
  as_of?: string | null
  include_outdated?: boolean
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

export interface SearchResult extends ContextFields {
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
  /** Knowledge group (related incidents) this result belongs to, if any. */
  group_id: string | null
  /** Self-reported troubleshooting feedback; display only, never used for ranking. */
  feedback: FeedbackSummary | null
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
  /** Groups of related incidents behind the results (individual results stay listed). */
  related_groups: GroupBrief[]
}

// ---- knowledge consolidation (related knowledge and groups) ------------------------------

export type RelationshipType =
  | 'same_problem'
  | 'supporting_evidence'
  | 'same_problem_different_conditions'
  | 'different_outcome'
  | 'potentially_conflicting'
  | 'related_symptoms'
  | 'unrelated'

export interface CaseRef {
  id: string
  title: string
  resolution_status: ResolutionStatus
  approval_status: ApprovalStatus
  conversation: string | null
  source_name: string | null
  thread_id: string | null
}

export interface RelationshipEvidence {
  message_id: string
  author: string
  sent_at: string
  excerpt: string
  source_url: string | null
}

export interface ConditionDifference {
  field: string
  /** null = not stated in that conversation (unknown, never assumed equal). */
  source_value: string | null
  target_value: string | null
}

export interface KnowledgeRelationship {
  id: string
  relationship_type: RelationshipType
  outcome_comparison: 'same_outcome' | 'different_outcome' | 'not_comparable' | null
  explanation: string | null
  source: CaseRef
  target: CaseRef
  shared_symptoms: string[]
  shared_equipment: string[]
  conditions: ConditionDifference[]
  unknown_conditions: string[]
  source_evidence: RelationshipEvidence[]
  target_evidence: RelationshipEvidence[]
  validation_notes: string[]
  model_name: string | null
  updated_at: string
}

export interface GroupBrief {
  id: string
  title: string
  summary: string | null
  case_count: number
  independent_conversations: number
  solution_count: number
  successful_paths: number
  conflict_count: number
  summary_pending: boolean
  review_status: 'unreviewed'
  updated_at: string
}

export interface SolutionPath {
  description: string
  outcome: 'successful' | 'unsuccessful' | 'mixed' | 'unknown'
  conditions: string[]
  knowledge_ids: string[]
}

export interface GroupMember extends CaseRef {
  problem_description: string
  knowledge_type: KnowledgeType
  valid_to: string | null
  superseded_by_id: string | null
  resolution: string | null
  equipment: string[]
  applicability_conditions: string[]
  evidence_count: number
}

export interface GroupDetail extends GroupBrief {
  shared_problem: string | null
  shared_symptoms: string[]
  known_environment: string[]
  solutions: SolutionPath[]
  failed_attempts: string[]
  contradictions: string[]
  missing_information: string[]
  summary_model: string | null
  generated_at: string | null
  members: GroupMember[]
}

export interface RelatedKnowledge {
  knowledge_id: string
  group: GroupBrief | null
  relationships: KnowledgeRelationship[]
}

// ---- troubleshooting feedback (real-world validation) -----------------------------------

export type FeedbackOutcome =
  'resolved' | 'not_resolved' | 'partially_resolved' | 'unknown' | 'not_attempted'

export interface FeedbackInput {
  attempted: boolean
  outcome?: Exclude<FeedbackOutcome, 'not_attempted'>
  equipment_identifier?: string
  firmware_version?: string
  environment_details?: Record<string, string>
  engineer_notes?: string
}

export interface FeedbackCreate extends FeedbackInput {
  troubleshooting_session_id: string
  guide_node_id: string
  knowledge_item_id: string
}

export interface TroubleshootingFeedback {
  id: string
  origin: 'troubleshooting_feedback'
  troubleshooting_session_id: string
  guide_node_id: string
  recommendation: string
  knowledge_item_id: string
  knowledge_title: string
  attempted: boolean
  outcome: FeedbackOutcome
  equipment_identifier: string | null
  firmware_version: string | null
  environment_details: Record<string, string> | null
  engineer_notes: string | null
  verification_status: 'self_reported' | 'independently_verified'
  relation_to_original:
    'supports' | 'contradicts' | 'mixed' | 'new_evidence' | 'no_attempt' | 'inconclusive'
  submitted_at: string
  updated_at: string
  revision: number
}

export interface FeedbackSaved extends TroubleshootingFeedback {
  created: boolean
  /** Only on creation; required to correct the feedback later. */
  edit_token: string | null
}

export interface OutcomeCounts {
  resolved: number
  not_resolved: number
  partially_resolved: number
  unknown: number
  not_attempted: number
}

export interface ConditionBreakdown {
  value: string | null
  counts: OutcomeCounts
}

export interface FeedbackSummary {
  knowledge_item_id: string
  sessions: number
  attempts: number
  counts: OutcomeCounts
  independently_verified: number
  has_conflicting_reports: boolean
  success_rate: number | null
  min_sample_for_rate: number
  by_firmware: ConditionBreakdown[]
  by_equipment: ConditionBreakdown[]
  condition_notes: string[]
  last_reported_at: string | null
  note: string
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

// ---- integrations (Slack) ----------------------------------------------------------------

export type SlackStatusValue =
  | 'disabled'
  | 'not_configured'
  | 'worker_not_running'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error'

export interface SlackChannel {
  channel_id: string
  name: string
  monitored: boolean
  bot_is_member: boolean | null
  source_id: string | null
}

export interface SlackStatus {
  enabled: boolean
  bot_token_configured: boolean
  app_token_configured: boolean
  signing_secret_configured: boolean
  status: SlackStatusValue
  connected: boolean
  credentials_verified: boolean
  worker_running: boolean
  connection_mode: string
  workspace_id: string | null
  workspace_name: string | null
  monitored_channels: SlackChannel[]
  last_event_at: string | null
  last_ingested_at: string | null
  heartbeat_at: string | null
  last_error: string | null
  next_steps: string[]
}

export interface SlackChannelList {
  monitored: SlackChannel[]
  available: SlackChannel[]
  available_error: string | null
}

export interface IntegrationEvent {
  id: string
  created_at: string
  kind: string
  level: 'info' | 'success' | 'warning' | 'error'
  message: string
  channel_id: string | null
  thread_id: string | null
}

// ---- email source and network inventory ----------------------------------------------------

export interface Mailbox {
  id: string
  name: string
  mailbox: string
  enabled: boolean
  threads: number
  messages: number
}

export interface EmailImportResult {
  mailbox: string
  imported: number
  duplicates: number
  threads: { id: string; title: string }[]
  skipped_reason: string | null
  note: string
}

export interface InventorySite {
  site_identifier: string
  name: string | null
  region: string | null
  description: string | null
  knowledge_count: number
}

export interface InventoryNode {
  equipment_identifier: string
  equipment_type: string | null
  vendor: string | null
  model: string | null
  unit_class: string | null
  installed_year: number | null
  site_identifier: string | null
  knowledge_count: number
  class_knowledge_count: number
}

export interface Inventory {
  sites: InventorySite[]
  nodes: InventoryNode[]
  note: string
}

export interface EmailConnection {
  id: string
  host: string
  port: number
  username: string
  folder: string
  since_days: number
  max_per_poll: number
  enabled: boolean
  status: 'connected' | 'error' | 'connecting'
  last_error: string | null
  last_checked_at: string | null
  imported_count: number
  folder_message_count: number | null
}

export interface EmailConnectionCreate {
  host: string
  port: number
  username: string
  password: string
  folder: string
  since_days: number
  max_per_poll: number
}

export interface EmailCheckResult {
  status: string
  fetched: number
  imported: number
  duplicates: number
  remaining: number
  threads: string[]
  error: string | null
}
