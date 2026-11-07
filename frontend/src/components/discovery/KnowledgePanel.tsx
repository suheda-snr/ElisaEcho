import {
  BrainCircuit,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  Database,
  LoaderCircle,
  RotateCw,
  ShieldAlert,
} from 'lucide-react'
import type { ReactNode } from 'react'

import {
  classificationLabels,
  evidenceLabels,
  formatTime,
  outcomeLabels,
  processingLabels,
  resolutionLabels,
} from '@/components/discovery/labels'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { KnowledgeItemDetail, Message, ThreadDiscovery } from '@/types/api'

interface KnowledgePanelProps {
  thread: ThreadDiscovery | null
  item: KnowledgeItemDetail | undefined
  itemLoading: boolean
  itemError: unknown
  messages: Message[]
  geminiConfigured: boolean
  /** Development-only manual re-analysis, offered when the last analysis failed. */
  onRetry?: () => void
  retrying?: boolean
  retryError?: unknown
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h3>
      {children}
    </section>
  )
}

function MessageRefs({ ids, messages }: { ids: string[]; messages: Message[] }) {
  const position = new Map(messages.map((m, i) => [m.id, i + 1]))
  return (
    <span className="inline-flex flex-wrap gap-1">
      {ids.map((id) => (
        <a
          key={id}
          href={`#message-${id}`}
          className="rounded border bg-muted px-1.5 font-mono text-xs text-muted-foreground hover:text-foreground"
        >
          #{position.get(id) ?? '?'}
        </a>
      ))}
    </span>
  )
}

function ConfidenceBar({ value }: { value: number }) {
  const percent = Math.round(value * 100)
  return (
    <div className="flex items-center gap-3">
      <div
        className="h-2 flex-1 overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label="Model confidence"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-medium text-foreground tabular-nums">
        {percent}%
      </span>
    </div>
  )
}

function ResolutionBadge({ status }: { status: KnowledgeItemDetail['resolution_status'] }) {
  const confirmed = status === 'confirmed_in_conversation'
  const Icon = confirmed ? CircleCheck : CircleDashed
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        confirmed
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
          : 'bg-muted text-foreground',
      )}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {resolutionLabels[status]}
    </span>
  )
}

export function KnowledgePanel({
  thread,
  item,
  itemLoading,
  itemError,
  messages,
  geminiConfigured,
  onRetry,
  retrying = false,
  retryError,
}: KnowledgePanelProps) {
  if (!thread) {
    return (
      <EmptyState icon={BrainCircuit}>
        Select a conversation to see what the AI discovered in it.
      </EmptyState>
    )
  }

  const candidate = thread.candidate
  const status = thread.processing_status

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={status === 'failed' ? 'destructive' : 'secondary'}>
          {status === 'processing' && <LoaderCircle className="animate-spin" aria-hidden="true" />}
          {processingLabels[status]}
        </Badge>
        {candidate && (
          <Badge variant="outline">
            {classificationLabels[candidate.classification] ?? candidate.classification}
          </Badge>
        )}
        {candidate?.analyzed_at && (
          <span className="text-xs text-muted-foreground">
            Analyzed {formatTime(candidate.analyzed_at)} · {candidate.analyzed_message_count}{' '}
            messages
          </span>
        )}
      </div>

      {status === 'failed' && candidate && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            The latest analysis failed (Gemini was unavailable). Showing the previous result, based
            on {candidate.analyzed_message_count} of {thread.message_count} messages. Retry to
            include the newer messages.
          </span>
        </div>
      )}

      {status === 'failed' && onRetry && (
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
            <RotateCw className={retrying ? 'animate-spin' : undefined} aria-hidden="true" />
            {retrying ? 'Analyzing…' : 'Retry analysis'}
          </Button>
          {retryError != null && (
            <span className="text-sm text-red-700">{getErrorMessage(retryError)}</span>
          )}
        </div>
      )}

      {!candidate && (
        <EmptyState icon={status === 'failed' || !geminiConfigured ? CircleAlert : LoaderCircle}>
          {status === 'failed'
            ? 'The last analysis failed. Nothing was stored for this conversation.'
            : geminiConfigured
              ? 'Waiting for the conversation to settle before analysis…'
              : 'Gemini is not configured, so this conversation cannot be analyzed yet.'}
        </EmptyState>
      )}

      {candidate?.detection_status === 'rejected' && (
        <EmptyState icon={CircleDashed}>
          No operational knowledge found. This conversation was ignored and nothing was added to the
          knowledge base.
          {candidate.summary && (
            <span className="mt-2 block text-xs">AI rationale: {candidate.summary}</span>
          )}
        </EmptyState>
      )}

      {candidate && candidate.detection_status === 'incomplete' && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-medium">Technical issue detected, no reusable fix yet</p>
          <p className="mt-1">{candidate.summary}</p>
          <p className="mt-2 text-xs">
            Stored as a candidate. It becomes knowledge once the conversation contains a fix.
          </p>
        </div>
      )}

      {candidate?.confidence != null && candidate.detection_status !== 'rejected' && (
        <Section title="Model confidence (not verification)">
          <ConfidenceBar value={candidate.confidence} />
        </Section>
      )}

      {candidate?.knowledge_item_id && (
        <>
          {itemLoading && !item && (
            <p className="text-sm text-muted-foreground">Loading knowledge…</p>
          )}
          {Boolean(itemError) && !item && (
            <p className="text-sm text-red-700">{getErrorMessage(itemError)}</p>
          )}
          {item && <KnowledgeDetail item={item} messages={messages} />}
        </>
      )}

      {candidate && candidate.flags.length > 0 && (
        <Section title="Server-side validation">
          <ul className="flex flex-col gap-1.5">
            {candidate.flags.map((flag) => (
              <li key={flag} className="flex gap-2 text-sm text-amber-900">
                <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {flag}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}

function KnowledgeDetail({ item, messages }: { item: KnowledgeItemDetail; messages: Message[] }) {
  return (
    <>
      <div className="flex flex-col gap-2">
        <h3 className="text-base font-semibold text-foreground">{item.title}</h3>
        <div className="flex flex-wrap items-center gap-2">
          <ResolutionBadge status={item.resolution_status} />
          <Badge variant="outline">
            {item.approval_status === 'unreviewed'
              ? 'Unreviewed: not an approved procedure'
              : `Expert review: ${item.approval_status}`}
          </Badge>
        </div>
      </div>

      <Section title="Problem">
        <p className="text-sm text-foreground">{item.problem_description}</p>
        {item.symptoms.length > 0 && (
          <ul className="list-disc pl-5 text-sm text-muted-foreground">
            {item.symptoms.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        )}
        {item.equipment.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {item.equipment.map((e) => (
              <Badge key={e.id} variant="secondary" className="font-mono">
                {e.equipment_identifier}
              </Badge>
            ))}
          </div>
        )}
      </Section>

      {item.attempted_actions.length > 0 && (
        <Section title="Attempted and suggested fixes">
          <ol className="flex flex-col gap-2">
            {item.attempted_actions.map((action, i) => (
              <li key={`${action.action}-${i}`} className="rounded-lg border bg-background p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <span className="text-sm font-medium text-foreground">{action.action}</span>
                  <Badge variant={action.outcome === 'successful' ? 'default' : 'outline'}>
                    {outcomeLabels[action.outcome]}
                  </Badge>
                </div>
                <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
                  Source messages <MessageRefs ids={action.message_ids} messages={messages} />
                </div>
              </li>
            ))}
          </ol>
        </Section>
      )}

      {item.resolution && (
        <Section title="Resolution">
          <p className="text-sm text-foreground">{item.resolution}</p>
        </Section>
      )}

      {item.applicability_conditions.length > 0 && (
        <Section title="Applicability and warnings">
          <ul className="list-disc pl-5 text-sm text-foreground">
            {item.applicability_conditions.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Evidence">
        <ul className="flex flex-col gap-1.5">
          {item.evidence.map((e) => (
            <li key={e.id} className="flex items-start gap-2 text-sm">
              <MessageRefs ids={[e.message.id]} messages={messages} />
              <span>
                <span className="font-medium text-foreground">
                  {evidenceLabels[e.evidence_type]}
                </span>
                {e.explanation && <span className="text-muted-foreground">: {e.explanation}</span>}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      {item.discovery && item.discovery.missing_information.length > 0 && (
        <Section title="Missing information">
          <ul className="list-disc pl-5 text-sm text-muted-foreground">
            {item.discovery.missing_information.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </Section>
      )}

      <div className="flex items-start gap-2 rounded-lg border bg-muted/40 p-3 text-xs text-muted-foreground">
        <Database className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <span>
          Saved to PostgreSQL as knowledge item{' '}
          <span className="font-mono text-foreground">{item.id.slice(0, 8)}</span> with{' '}
          {item.evidence.length} evidence links · updated {formatTime(item.updated_at)}
          {item.discovery?.model_name && ` · model ${item.discovery.model_name}`}
        </span>
      </div>
    </>
  )
}

function EmptyState({ icon: Icon, children }: { icon: typeof BrainCircuit; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
      <Icon className="size-6" aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}
