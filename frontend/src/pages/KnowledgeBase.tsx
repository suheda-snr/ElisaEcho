import {
  CircleCheck,
  CircleDashed,
  MessageSquareQuote,
  Search as SearchIcon,
  ShieldAlert,
  Workflow,
} from 'lucide-react'
import { type ReactNode, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import {
  classificationLabels,
  evidenceLabels,
  formatTime,
  outcomeLabels,
  resolutionLabels,
} from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useKnowledgeItem, useKnowledgeItems } from '@/hooks/useDiscovery'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { KnowledgeItemDetail, ResolutionStatus } from '@/types/api'

type Filter = 'all' | ResolutionStatus

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'confirmed_in_conversation', label: 'Confirmed in chat' },
  { value: 'suggested', label: 'Suggested' },
  { value: 'unknown', label: 'Unclear' },
]

export default function KnowledgeBase() {
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<Filter>('all')
  const list = useKnowledgeItems(false)
  const items = useMemo(
    () =>
      (list.data?.items ?? []).filter((k) => filter === 'all' || k.resolution_status === filter),
    [list.data, filter],
  )
  const selectedId = params.get('item') ?? items[0]?.id ?? null
  const detail = useKnowledgeItem(selectedId, false)

  return (
    <div className="flex flex-col gap-6">
      <PageHeader description="Operational knowledge the AI discovered in conversations. Each entry keeps the original messages as evidence. Nothing here is an approved procedure until an expert reviews it." />

      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Filter by resolution"
      >
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            aria-pressed={filter === f.value}
            className={cn(
              'rounded-full border px-3 py-1 text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
              filter === f.value
                ? 'border-primary bg-primary text-primary-foreground'
                : 'bg-card hover:bg-muted',
            )}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-sm text-muted-foreground">
          {items.length} of {list.data?.total ?? 0} items
        </span>
      </div>

      {list.isError && <p className="text-sm text-red-700">{getErrorMessage(list.error)}</p>}

      {list.data && list.data.total === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-12 text-center text-sm text-muted-foreground">
            <CircleDashed className="size-6" aria-hidden="true" />
            Nothing has been discovered yet.
            <Button asChild>
              <Link to="/discovery">Run the live demo</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          <ul className="flex flex-col gap-2 lg:col-span-4" aria-label="Knowledge items">
            {items.map((k) => (
              <li key={k.id}>
                <button
                  type="button"
                  onClick={() => setParams({ item: k.id }, { replace: true })}
                  aria-pressed={k.id === selectedId}
                  className={cn(
                    'flex w-full flex-col gap-1.5 rounded-xl border bg-card p-3 text-left transition-colors',
                    'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                    k.id === selectedId
                      ? 'border-primary/50 ring-1 ring-primary/30'
                      : 'hover:bg-muted/40',
                  )}
                >
                  <span className="text-sm font-medium text-foreground">{k.title}</span>
                  <span className="line-clamp-2 text-xs text-muted-foreground">
                    {k.problem_description}
                  </span>
                  <span className="flex flex-wrap gap-1.5">
                    <ResolutionBadge status={k.resolution_status} />
                    <Badge variant="outline">
                      {k.approval_status === 'approved' ? 'Expert-approved' : 'Not reviewed'}
                    </Badge>
                  </span>
                </button>
              </li>
            ))}
            {items.length === 0 && list.data && (
              <li className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                No items match this filter.
              </li>
            )}
          </ul>

          <div className="lg:col-span-8">
            {detail.isError && (
              <p className="text-sm text-red-700">{getErrorMessage(detail.error)}</p>
            )}
            {detail.data ? (
              <KnowledgeView item={detail.data} />
            ) : (
              selectedId && <p className="text-sm text-muted-foreground">Loading…</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function ResolutionBadge({ status }: { status: ResolutionStatus }) {
  const confirmed = status === 'confirmed_in_conversation'
  const Icon = confirmed ? CircleCheck : CircleDashed
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        confirmed
          ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
          : 'bg-muted text-foreground',
      )}
    >
      <Icon className="size-3" aria-hidden="true" />
      {resolutionLabels[status]}
    </span>
  )
}

function Section({
  title,
  children,
  className,
}: {
  title: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={cn('flex flex-col gap-2', className)}>
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h3>
      {children}
    </section>
  )
}

function KnowledgeView({ item }: { item: KnowledgeItemDetail }) {
  const confirmed = item.resolution_status === 'confirmed_in_conversation'
  const evidence = [...item.evidence].sort((a, b) =>
    a.message.sent_at.localeCompare(b.message.sent_at),
  )
  const position = new Map(evidence.map((e, i) => [e.message.id, i + 1]))
  const discovery = item.discovery

  return (
    <Card>
      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold text-foreground">{item.title}</h2>
          <div className="flex flex-wrap items-center gap-1.5">
            <ResolutionBadge status={item.resolution_status} />
            <Badge variant="outline">
              {item.approval_status === 'approved' ? 'Expert-approved' : 'Not expert-reviewed'}
            </Badge>
            {[
              ...item.equipment.map((e) => e.equipment_identifier),
              ...item.incidents.map((i) => i.incident_number),
            ].map((id) => (
              <Badge key={id} variant="secondary" className="font-mono">
                {id}
              </Badge>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to={`/search?q=${encodeURIComponent(item.problem_description)}`}>
                <SearchIcon aria-hidden="true" />
                Find similar issues
              </Link>
            </Button>
            <Button size="sm" asChild>
              <Link to={`/troubleshoot?problem=${encodeURIComponent(item.problem_description)}`}>
                <Workflow aria-hidden="true" />
                Build a troubleshooting guide
              </Link>
            </Button>
          </div>
        </div>

        {item.approval_status !== 'approved' && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              {confirmed
                ? 'Engineers reported in chat that this worked. It is not an approved procedure; check it applies before using it.'
                : 'This fix was suggested in a conversation but nobody confirmed that it worked.'}
            </span>
          </div>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <Section title="Problem">
            <p className="text-sm text-foreground">{item.problem_description}</p>
            {item.symptoms.length > 0 && (
              <ul className="list-disc pl-5 text-sm text-muted-foreground">
                {item.symptoms.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            )}
            {item.root_cause && (
              <p className="text-sm text-muted-foreground">Root cause: {item.root_cause}</p>
            )}
          </Section>
          <Section title={confirmed ? 'Fix (confirmed in chat)' : 'Suggested fix'}>
            <p className="text-sm font-medium text-foreground">
              {item.resolution ?? 'No fix recorded'}
            </p>
            {item.applicability_conditions.length > 0 && (
              <ul className="list-disc pl-5 text-sm text-muted-foreground">
                {item.applicability_conditions.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        {item.attempted_actions.length > 0 && (
          <Section title="What was tried">
            <ol className="flex flex-col gap-2">
              {item.attempted_actions.map((a, i) => (
                <li
                  key={`${a.action}-${i}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-background px-3 py-2"
                >
                  <span className="text-sm text-foreground">{a.action}</span>
                  <span className="flex items-center gap-1.5">
                    {a.message_ids
                      .filter((id) => position.has(id))
                      .map((id) => (
                        <span
                          key={id}
                          className="rounded border bg-muted px-1.5 font-mono text-xs text-muted-foreground"
                        >
                          #{position.get(id)}
                        </span>
                      ))}
                    <Badge variant={a.outcome === 'successful' ? 'default' : 'outline'}>
                      {outcomeLabels[a.outcome]}
                    </Badge>
                  </span>
                </li>
              ))}
            </ol>
          </Section>
        )}

        <Section title={`Evidence (${evidence.length} messages)`}>
          {evidence.length === 0 ? (
            <p className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
              No supporting messages are linked. Treat with extra caution.
            </p>
          ) : (
            <ol className="flex flex-col gap-3">
              {evidence.map((e) => (
                <li key={e.id}>
                  <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-xs">
                    <span className="font-mono text-muted-foreground">
                      #{position.get(e.message.id)}
                    </span>
                    <span className="font-medium text-foreground">
                      {e.message.author_display_name ?? e.message.author_external_id}
                    </span>
                    <span className="text-muted-foreground">{formatTime(e.message.sent_at)}</span>
                    <Badge variant="outline">{evidenceLabels[e.evidence_type]}</Badge>
                  </div>
                  <blockquote className="flex gap-2 rounded-lg border-l-2 border-primary/40 bg-muted/40 px-3 py-2 text-sm text-foreground">
                    <MessageSquareQuote
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    {e.message.deleted_at ? (
                      <span className="text-muted-foreground italic">
                        Message deleted at the source.
                      </span>
                    ) : (
                      <span className="whitespace-pre-wrap">{e.message.content}</span>
                    )}
                  </blockquote>
                  {e.explanation && (
                    <p className="mt-1 text-xs text-muted-foreground">{e.explanation}</p>
                  )}
                </li>
              ))}
            </ol>
          )}
        </Section>

        {discovery && (
          <div className="grid gap-4 rounded-lg border bg-muted/30 p-4 text-sm md:grid-cols-2">
            <Section title="How it was found">
              <p className="text-foreground">
                {classificationLabels[discovery.classification] ?? discovery.classification}
              </p>
              <p className="text-xs text-muted-foreground">
                {discovery.model_name} · analyzed {formatTime(discovery.analyzed_at)}
                {discovery.model_confidence != null &&
                  ` · model confidence ${Math.round(discovery.model_confidence * 100)}% (not verification)`}
              </p>
              {discovery.validation_flags.map((f) => (
                <p key={f} className="text-xs text-amber-800">
                  {f}
                </p>
              ))}
            </Section>
            <Section title="Missing information">
              {discovery.missing_information.length === 0 ? (
                <p className="text-muted-foreground">None reported.</p>
              ) : (
                <ul className="list-disc pl-5 text-muted-foreground">
                  {discovery.missing_information.map((m) => (
                    <li key={m}>{m}</li>
                  ))}
                </ul>
              )}
            </Section>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
