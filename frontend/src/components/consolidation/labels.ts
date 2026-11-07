import type { RelationshipType, SolutionPath } from '@/types/api'

export type RelationTone = 'support' | 'conflict' | 'conditions' | 'weak'

export const relationshipInfo: Record<
  RelationshipType,
  { label: string; tone: RelationTone; hint: string }
> = {
  supporting_evidence: {
    label: 'Supporting evidence',
    tone: 'support',
    hint: 'Another conversation independently reports the same fix working.',
  },
  same_problem: {
    label: 'Same problem',
    tone: 'support',
    hint: 'The same underlying problem was discussed in another conversation.',
  },
  same_problem_different_conditions: {
    label: 'Same problem, different conditions',
    tone: 'conditions',
    hint: 'Same problem, but equipment, firmware or configuration differ.',
  },
  different_outcome: {
    label: 'Different outcome',
    tone: 'conflict',
    hint: 'The same action was tried with a different result.',
  },
  potentially_conflicting: {
    label: 'Potentially conflicting',
    tone: 'conflict',
    hint: 'The recommendations contradict each other.',
  },
  related_symptoms: {
    label: 'Similar symptoms only',
    tone: 'weak',
    hint: 'Symptoms overlap, but the cause may differ. Suggested only; not grouped.',
  },
  unrelated: { label: 'Unrelated', tone: 'weak', hint: '' },
}

export const toneClasses: Record<RelationTone, string> = {
  support: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  conflict: 'border-amber-300 bg-amber-50 text-amber-900',
  conditions: 'border-sky-200 bg-sky-50 text-sky-900',
  weak: 'bg-muted text-muted-foreground',
}

export const solutionOutcomeLabels: Record<SolutionPath['outcome'], string> = {
  successful: 'Worked',
  unsuccessful: 'Did not work',
  mixed: 'Worked in some cases',
  unknown: 'Outcome unknown',
}

export const solutionOutcomeClasses: Record<SolutionPath['outcome'], string> = {
  successful: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  unsuccessful: 'border-red-200 bg-red-50 text-red-800',
  mixed: 'border-amber-300 bg-amber-50 text-amber-900',
  unknown: 'bg-muted text-muted-foreground',
}

/** "3 related incidents, 2 distinct resolution paths" */
export function groupHeadline(g: { case_count: number; solution_count: number }): string {
  const cases = `${g.case_count} related incident${g.case_count === 1 ? '' : 's'}`
  if (g.solution_count === 0) return cases
  return `${cases}, ${g.solution_count} distinct resolution path${g.solution_count === 1 ? '' : 's'}`
}
