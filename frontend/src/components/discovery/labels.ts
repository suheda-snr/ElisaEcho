import type { AttemptedAction, EvidenceType, ProcessingStatus, ResolutionStatus } from '@/types/api'

export const classificationLabels: Record<string, string> = {
  irrelevant: 'Irrelevant conversation',
  incident_without_resolution: 'Incident, no resolution yet',
  unverified_suggestion: 'Unverified suggestion',
  confirmed_resolution: 'Confirmed resolution',
  workaround_or_exception: 'Workaround or exception',
  contradictory_or_incomplete: 'Contradictory or incomplete',
  access_information: 'Site access information',
}

export const processingLabels: Record<ProcessingStatus, string> = {
  pending: 'Waiting for analysis',
  processing: 'Analyzing…',
  processed: 'Analyzed',
  failed: 'Analysis failed',
}

export const resolutionLabels: Record<ResolutionStatus, string> = {
  unknown: 'Resolution unknown',
  suggested: 'Suggested, not confirmed',
  confirmed_in_conversation: 'Confirmed in conversation',
}

export const evidenceLabels: Record<EvidenceType, string> = {
  problem_report: 'Problem report',
  attempted_fix: 'Attempted fix',
  suggested_solution: 'Suggested solution',
  confirmed_resolution: 'Confirms the fix worked',
  applicability_condition: 'Applicability condition',
}

export const outcomeLabels: Record<AttemptedAction['outcome'], string> = {
  successful: 'Worked',
  unsuccessful: 'Did not work',
  partially_successful: 'Partly worked',
  not_attempted: 'Proposed, not tried',
  unknown: 'Outcome unknown',
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
