import type { FeedbackOutcome, FeedbackSummary, TroubleshootingFeedback } from '@/types/api'

export const outcomeLabels: Record<FeedbackOutcome, string> = {
  resolved: 'Resolved',
  not_resolved: 'Not resolved',
  partially_resolved: 'Partially resolved',
  unknown: 'Outcome unknown',
  not_attempted: 'Not attempted',
}

export const outcomeHints: Record<Exclude<FeedbackOutcome, 'not_attempted'>, string> = {
  resolved: 'The issue was fixed',
  not_resolved: 'The issue remains',
  partially_resolved: 'Symptoms improved, but the issue remains',
  unknown: 'Could not determine the outcome',
}

export const outcomeClasses: Record<FeedbackOutcome, string> = {
  resolved: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  not_resolved: 'border-red-200 bg-red-50 text-red-800',
  partially_resolved: 'border-amber-300 bg-amber-50 text-amber-900',
  unknown: 'bg-muted text-muted-foreground',
  not_attempted: 'bg-muted text-muted-foreground',
}

export const relationLabels: Record<TroubleshootingFeedback['relation_to_original'], string> = {
  supports: 'Supports the original conversation',
  contradicts: 'Contradicts the original report',
  mixed: 'Partly supports the original report',
  new_evidence: 'First report that the fix works',
  no_attempt: 'Not attempted',
  inconclusive: 'Inconclusive',
}

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`

/** e.g. "Reported resolved in 3 troubleshooting sessions; not resolved in 1." */
export function feedbackSentence(s: FeedbackSummary): string {
  const c = s.counts
  const entries: [string, number][] = (
    [
      ['resolved', c.resolved],
      ['not resolved', c.not_resolved],
      ['partially resolved', c.partially_resolved],
      ['outcome unknown', c.unknown],
    ] as [string, number][]
  ).filter(([, n]) => n > 0)
  if (entries.length === 0) {
    return c.not_attempted
      ? `Not attempted in ${plural(c.not_attempted, 'troubleshooting session')}.`
      : 'No feedback yet.'
  }
  const parts = entries.map(([label, n], i) =>
    i === 0 ? `${label} in ${plural(n, 'troubleshooting session')}` : `${label} in ${n}`,
  )
  return `Reported ${parts.join('; ')}.`
}
