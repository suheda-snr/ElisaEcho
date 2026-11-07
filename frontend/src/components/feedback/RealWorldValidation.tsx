import { BadgeCheck, MessageSquareQuote, ShieldQuestion, Users } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { formatTime } from '@/components/discovery/labels'
import { useFeedbackSummary, useKnowledgeFeedback } from '@/hooks/useFeedback'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { ConditionBreakdown, KnowledgeItemDetail, OutcomeCounts } from '@/types/api'

import { feedbackSentence, outcomeClasses, outcomeLabels, relationLabels } from './labels'

/**
 * Real-world validation of one knowledge item. Four separate concepts are shown side by side
 * and never merged into one badge: confirmed in conversation, self-reported applications,
 * independently verified outcomes, and formal expert approval.
 */
export function RealWorldValidation({ item }: { item: KnowledgeItemDetail }) {
  const summary = useFeedbackSummary(item.id)
  const records = useKnowledgeFeedback(item.id)
  const s = summary.data
  const confirmed = item.resolution_status === 'confirmed_in_conversation'

  return (
    <section id="validation" className="flex flex-col gap-3" aria-labelledby="validation-title">
      <h3 id="validation-title" className="text-[13px] font-semibold text-foreground">
        Real-world validation
      </h3>

      <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <Status
          icon={<MessageSquareQuote className="size-4" aria-hidden="true" />}
          label="Original conversation"
          value={confirmed ? 'Confirmed in conversation' : 'Not confirmed in conversation'}
          detail={`${item.evidence.length} message(s) as evidence`}
          tone={confirmed ? 'good' : 'neutral'}
        />
        <Status
          icon={<Users className="size-4" aria-hidden="true" />}
          label="Self-reported applications"
          value={s ? `${s.counts.resolved} resolved · ${s.counts.not_resolved} not resolved` : '–'}
          detail={s ? `${s.attempts} attempt(s) in ${s.sessions} session(s)` : undefined}
          tone={
            s?.has_conflicting_reports ? 'warn' : s && s.counts.resolved > 0 ? 'good' : 'neutral'
          }
        />
        <Status
          icon={<ShieldQuestion className="size-4" aria-hidden="true" />}
          label="Independently verified"
          value={s ? `${s.independently_verified} outcome(s)` : '–'}
          detail="No verification workflow yet"
          tone="neutral"
        />
        <Status
          icon={<BadgeCheck className="size-4" aria-hidden="true" />}
          label="Formal approval"
          value={item.approval_status === 'approved' ? 'Approved procedure' : 'Not approved'}
          detail="Feedback never changes this"
          tone={item.approval_status === 'approved' ? 'good' : 'neutral'}
        />
      </dl>

      {summary.isError && <p className="text-sm text-red-700">{getErrorMessage(summary.error)}</p>}
      {s && s.sessions === 0 && (
        <p className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
          Nobody has reported using this knowledge in a guided troubleshooting session yet.
        </p>
      )}

      {s && s.sessions > 0 && (
        <div className="flex flex-col gap-3 rounded-lg border bg-background p-3">
          <p className="text-sm font-medium text-foreground">{feedbackSentence(s)}</p>
          {s.success_rate !== null ? (
            <p className="text-xs text-muted-foreground">
              {Math.round(s.success_rate * 100)}% of {s.attempts} self-reported attempts resolved
              the issue. This is not a measured success probability.
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              No percentage shown: fewer than {s.min_sample_for_rate} attempts reported.
            </p>
          )}
          {s.condition_notes.length > 0 && (
            <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              <p className="font-medium">Outcomes differ by condition</p>
              <ul className="list-disc pl-5">
                {s.condition_notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-2">
            <BreakdownTable title="By firmware" rows={s.by_firmware} />
            <BreakdownTable title="By equipment" rows={s.by_equipment} />
          </div>
          <p className="text-xs text-muted-foreground">Self-reported by engineers.</p>
        </div>
      )}

      {records.data && records.data.items.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
            Individual feedback records ({records.data.total})
          </summary>
          <ol className="mt-2 flex flex-col gap-2">
            {records.data.items.map((f) => (
              <li
                key={f.id}
                className="flex flex-col gap-1 rounded-lg border bg-background px-3 py-2 text-sm"
              >
                <div className="flex flex-wrap items-center gap-1.5">
                  <span
                    className={cn(
                      'rounded-full border px-2 py-0.5 text-xs font-medium',
                      outcomeClasses[f.outcome],
                    )}
                  >
                    {outcomeLabels[f.outcome]}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {relationLabels[f.relation_to_original]}
                  </span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {formatTime(f.updated_at)}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">
                  Step “{f.recommendation}” ·{' '}
                  {[f.equipment_identifier, f.firmware_version && `firmware ${f.firmware_version}`]
                    .filter(Boolean)
                    .join(' · ') || 'conditions not reported'}
                  {f.environment_details?.details && ` · ${f.environment_details.details}`}
                </p>
                {f.engineer_notes && <p className="text-foreground">“{f.engineer_notes}”</p>}
                <p className="text-xs text-muted-foreground">
                  {f.verification_status === 'self_reported'
                    ? 'Self-reported'
                    : 'Independently verified'}
                  {f.revision > 1 && ` · corrected (revision ${f.revision})`} ·{' '}
                  <Link
                    to={`/troubleshoot?session=${f.troubleshooting_session_id}`}
                    className="underline hover:text-foreground"
                  >
                    open session
                  </Link>
                </p>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  )
}

const TONES = {
  good: 'border-emerald-200 bg-emerald-50/60',
  warn: 'border-amber-300 bg-amber-50/60',
  neutral: 'bg-muted/30',
}

function Status({
  icon,
  label,
  value,
  detail,
  tone,
}: {
  icon: ReactNode
  label: string
  value: string
  detail?: string
  tone: keyof typeof TONES
}) {
  return (
    <div className={cn('flex flex-col gap-0.5 rounded-lg border px-3 py-2', TONES[tone])}>
      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        {label}
      </dt>
      <dd className="text-sm font-medium text-foreground">{value}</dd>
      {detail && <dd className="text-xs text-muted-foreground">{detail}</dd>}
    </div>
  )
}

const COLUMNS: [keyof OutcomeCounts, string][] = [
  ['resolved', 'Resolved'],
  ['not_resolved', 'Not resolved'],
  ['partially_resolved', 'Partial'],
  ['unknown', 'Unknown'],
]

function BreakdownTable({ title, rows }: { title: string; rows: ConditionBreakdown[] }) {
  if (rows.length === 0) return null
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="pb-1 text-left text-xs font-semibold text-muted-foreground">
          {title}
        </caption>
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th className="py-1 pr-3 font-medium">Condition</th>
            {COLUMNS.map(([, label]) => (
              <th key={label} className="py-1 pr-2 text-right font-medium">
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.value ?? '__none'} className="border-t">
              <td className="py-1 pr-3">
                {r.value ? (
                  <span className="font-mono">{r.value}</span>
                ) : (
                  <span className="text-muted-foreground italic">not reported</span>
                )}
              </td>
              {COLUMNS.map(([key]) => (
                <td key={key} className="py-1 pr-2 text-right tabular-nums">
                  {r.counts[key] || <span className="text-muted-foreground">0</span>}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
