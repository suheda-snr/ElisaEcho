import { Inbox, MessageSquareQuote, Search as SearchIcon, Workflow } from 'lucide-react'
import { type ReactNode, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { Disclosure } from '@/components/common/Disclosure'
import { Insight } from '@/components/common/Insight'
import { EmptyState, Loading, Notice, SectionTitle } from '@/components/common/States'
import {
  EntityChips,
  ResolutionBadge,
  ReviewBadge,
  SourceBadge,
} from '@/components/common/StatusBadges'
import { RelatedKnowledgeSection } from '@/components/consolidation/RelatedKnowledgeSection'
import { ContextSection, KnowledgeTypeBadge, OutdatedBadge } from '@/components/context/ContextInfo'
import {
  classificationLabels,
  evidenceLabels,
  formatTime,
  outcomeLabels,
} from '@/components/discovery/labels'
import { RealWorldValidation } from '@/components/feedback/RealWorldValidation'
import { Button } from '@/components/ui/button'
import { useKnowledgeItem, useKnowledgeItems } from '@/hooks/useDiscovery'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { KnowledgeItemDetail, KnowledgeItemSummary } from '@/types/api'

type Filter = 'all' | 'confirmed' | 'suggested' | 'site_access' | 'outdated'

const FILTERS: { value: Filter; label: string; test: (k: KnowledgeItemSummary) => boolean }[] = [
  { value: 'all', label: 'All', test: () => true },
  {
    value: 'confirmed',
    label: 'Confirmed in chat',
    test: (k) => k.resolution_status === 'confirmed_in_conversation',
  },
  {
    value: 'suggested',
    label: 'Not confirmed',
    test: (k) => k.resolution_status !== 'confirmed_in_conversation',
  },
  { value: 'site_access', label: 'Site access', test: (k) => k.knowledge_type === 'site_access' },
  { value: 'outdated', label: 'Outdated', test: (k) => Boolean(k.valid_to) },
]

export default function KnowledgeBase() {
  const [params, setParams] = useSearchParams()
  const [filter, setFilter] = useState<Filter>('all')
  const [text, setText] = useState('')
  const list = useKnowledgeItems(false)
  const items = useMemo(() => {
    const test = FILTERS.find((f) => f.value === filter)!.test
    const needle = text.trim().toLowerCase()
    return (list.data?.items ?? []).filter(
      (k) =>
        test(k) &&
        (!needle ||
          [
            k.title,
            k.problem_description,
            k.conversation ?? '',
            ...k.entity_links.map((l) => l.label),
          ]
            .join(' ')
            .toLowerCase()
            .includes(needle)),
    )
  }, [list.data, filter, text])
  const selectedId = params.get('item') ?? items[0]?.id ?? null
  const detail = useKnowledgeItem(selectedId, false)

  if (list.data && list.data.total === 0) {
    return (
      <EmptyState
        icon={Inbox}
        title="Nothing discovered yet"
        action={
          <Button asChild>
            <Link to="/discovery">Open Live Discovery</Link>
          </Button>
        }
      >
        Knowledge appears here once a connected conversation contains a fix or operational context.
      </EmptyState>
    )
  }

  return (
    <div className="grid gap-5 lg:grid-cols-12">
      <div className="flex flex-col gap-3 lg:col-span-4">
        <input
          type="search"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Filter by title, node or site"
          aria-label="Filter knowledge"
          className="h-10 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        />
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter">
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
                  : 'bg-background hover:bg-muted',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
        {list.isError && <Notice tone="error">{getErrorMessage(list.error)}</Notice>}
        {list.isPending && <Loading />}
        <p className="text-sm text-muted-foreground">
          {items.length} of {list.data?.total ?? 0}
        </p>
        <ul
          className="divide-y overflow-hidden rounded-lg border bg-card"
          aria-label="Knowledge items"
        >
          {items.map((k) => (
            <li key={k.id}>
              <button
                type="button"
                onClick={() => setParams({ item: k.id }, { replace: true })}
                aria-pressed={k.id === selectedId}
                className={cn(
                  'flex w-full cursor-pointer flex-col gap-1.5 px-3.5 py-3 text-left transition-colors duration-150',
                  'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                  k.id === selectedId
                    ? 'bg-accent/70 shadow-[inset_3px_0_0_var(--primary)]'
                    : 'hover:bg-muted/50',
                )}
              >
                <span className="line-clamp-2 text-sm font-medium text-foreground">{k.title}</span>
                <EntityChips links={k.entity_links} max={2} />
                <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                  <ResolutionBadge status={k.resolution_status} />
                  <OutdatedBadge validTo={k.valid_to} />
                  <KnowledgeTypeBadge type={k.knowledge_type} />
                  <SourceBadge type={k.source_type} />
                </span>
              </button>
            </li>
          ))}
          {items.length === 0 && list.data && (
            <li className="p-4 text-sm text-muted-foreground">Nothing matches this filter.</li>
          )}
        </ul>
      </div>

      <div className="lg:col-span-8">
        {detail.isError && <Notice tone="error">{getErrorMessage(detail.error)}</Notice>}
        {detail.data ? <KnowledgeView item={detail.data} /> : selectedId && <Loading />}
      </div>
    </div>
  )
}

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <SectionTitle>{title}</SectionTitle>
      {children}
    </section>
  )
}

function KnowledgeView({ item }: { item: KnowledgeItemDetail }) {
  const confirmed = item.resolution_status === 'confirmed_in_conversation'
  const evidence = [...item.evidence].sort((a, b) =>
    a.message.sent_at.localeCompare(b.message.sent_at),
  )
  // One entry per message (a message can be cited for several roles).
  const messages = evidence.filter(
    (e, i) => evidence.findIndex((o) => o.message.id === e.message.id) === i,
  )
  const rolesOf = (id: string) =>
    evidence.filter((e) => e.message.id === id).map((e) => evidenceLabels[e.evidence_type])
  const position = new Map(messages.map((e, i) => [e.message.id, i + 1]))
  const discovery = item.discovery

  return (
    <article className="flex flex-col gap-6 rounded-lg border bg-card p-5">
      <Insight
        label={item.knowledge_type === 'site_access' ? 'Site access' : 'Discovered knowledge'}
        badges={
          <>
            <ResolutionBadge status={item.resolution_status} />
            <ReviewBadge status={item.approval_status} />
            <OutdatedBadge validTo={item.valid_to} />
          </>
        }
        title={item.title}
      >
        <div>
          <p className="text-xs font-medium text-insight-foreground">
            {item.knowledge_type === 'site_access'
              ? 'How to get access'
              : confirmed
                ? 'Fix, confirmed in chat'
                : 'Suggested fix'}
          </p>
          <p className="mt-0.5 text-[15px] leading-relaxed font-medium text-foreground">
            {item.resolution ?? 'No fix recorded'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button asChild>
            <Link to={`/troubleshoot?problem=${encodeURIComponent(item.problem_description)}`}>
              <Workflow aria-hidden="true" />
              Start troubleshooting
            </Link>
          </Button>
          <Button variant="outline" className="bg-card" asChild>
            <Link to={`/knowledge?q=${encodeURIComponent(item.problem_description)}`}>
              <SearchIcon aria-hidden="true" />
              Find similar
            </Link>
          </Button>
        </div>
      </Insight>

      <ContextSection context={item} />

      <div className="grid gap-6 md:grid-cols-2">
        <Block title="Problem">
          <p className="text-[15px] text-foreground">{item.problem_description}</p>
          {item.symptoms.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-foreground/80">
              {item.symptoms.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          {item.root_cause && (
            <p className="text-sm text-foreground/80">
              <span className="font-medium">Root cause:</span> {item.root_cause}
            </p>
          )}
        </Block>
        {item.applicability_conditions.length > 0 && (
          <Block title="When it applies">
            <ul className="flex flex-col gap-1 text-sm leading-relaxed text-foreground/85">
              {item.applicability_conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </Block>
        )}
      </div>

      {item.attempted_actions.length > 0 && (
        <Block title="What was tried">
          <ol className="flex flex-col divide-y rounded-lg border">
            {item.attempted_actions.map((a, i) => (
              <li
                key={`${a.action}-${i}`}
                className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"
              >
                <span className="text-sm text-foreground">{a.action}</span>
                <span className="flex items-center gap-1.5 text-xs">
                  {a.message_ids
                    .filter((id) => position.has(id))
                    .map((id) => (
                      <a
                        key={id}
                        href={`#evidence-${id}`}
                        className="rounded bg-muted px-1.5 font-mono text-muted-foreground hover:text-foreground"
                      >
                        #{position.get(id)}
                      </a>
                    ))}
                  <span
                    className={cn(
                      'font-medium',
                      a.outcome === 'successful'
                        ? 'text-emerald-700'
                        : a.outcome === 'unsuccessful'
                          ? 'text-red-700'
                          : 'text-muted-foreground',
                    )}
                  >
                    {outcomeLabels[a.outcome]}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </Block>
      )}

      <Block title={`Original messages (${messages.length})`}>
        {messages.length === 0 ? (
          <p className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
            No supporting messages are linked. Use with caution.
          </p>
        ) : (
          <ol className="flex flex-col gap-3">
            {messages.map((e) => (
              <li key={e.id} id={`evidence-${e.message.id}`} className="scroll-mt-24">
                <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-xs text-muted-foreground">
                  <span className="font-mono">#{position.get(e.message.id)}</span>
                  <span className="font-semibold text-foreground">
                    {e.message.author_display_name ?? e.message.author_external_id}
                  </span>
                  <span>{formatTime(e.message.sent_at)}</span>
                  <span>· {rolesOf(e.message.id).join(', ')}</span>
                </div>
                <blockquote className="flex gap-2 rounded-lg border-l-3 border-primary/50 bg-muted/50 px-3 py-2 text-sm leading-relaxed text-foreground">
                  <MessageSquareQuote
                    className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                  {e.message.deleted_at ? (
                    <span className="text-muted-foreground italic">Deleted at the source.</span>
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
      </Block>

      <RealWorldValidation item={item} />

      <RelatedKnowledgeSection itemId={item.id} />

      {discovery && (
        <Disclosure title="How it was found">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-muted-foreground">Classified as</dt>
            <dd>{classificationLabels[discovery.classification] ?? discovery.classification}</dd>
            <dt className="text-muted-foreground">Analyzed</dt>
            <dd>{formatTime(discovery.analyzed_at)}</dd>
            {discovery.model_name && (
              <>
                <dt className="text-muted-foreground">Model</dt>
                <dd className="font-mono text-xs">{discovery.model_name}</dd>
              </>
            )}
            <dt className="text-muted-foreground">Missing</dt>
            <dd>{discovery.missing_information.join('; ') || 'Nothing reported'}</dd>
          </dl>
          {discovery.validation_flags.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 text-sm text-amber-900">
              {discovery.validation_flags.map((f) => (
                <li key={f}>· {f}</li>
              ))}
            </ul>
          )}
        </Disclosure>
      )}
    </article>
  )
}
