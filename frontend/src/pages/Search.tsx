import {
  CircleAlert,
  CircleCheck,
  CircleDashed,
  LoaderCircle,
  MessageSquareQuote,
  Search as SearchIcon,
  ShieldAlert,
  Sparkles,
  Workflow,
} from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import {
  evidenceLabels,
  formatTime,
  outcomeLabels,
  resolutionLabels,
} from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useKnowledgeSearch } from '@/hooks/useSearch'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type {
  ApprovalStatus,
  ResolutionStatus,
  SearchRanking,
  SearchRequest,
  SearchResponse,
  SearchResult,
} from '@/types/api'

// Demonstration queries for the synthetic demo data. They are sent to the real search API;
// nothing about the answers is hardcoded.
const EXAMPLES = [
  'Connection keeps dropping after router restart',
  'Site 42 intermittent connectivity',
  'Restarting the device did not fix the issue',
  'Routing adjacency with the upstream provider keeps resetting',
  'PE-03',
]

const semanticNotes: Record<SearchResponse['retrieval']['semantic'], string | null> = {
  used: null,
  no_embeddings: 'No knowledge has been embedded yet, so only keyword and identifier matching ran.',
  unavailable:
    'Semantic search is unavailable right now, so only keyword and identifier matching ran.',
  not_configured: 'Gemini is not configured, so only keyword and identifier matching ran.',
}

export default function Search() {
  // The query lives in the URL (?q=...), so searches can be shared and survive reloads.
  const [params, setParams] = useSearchParams()
  const initial = params.get('q')?.trim() ?? ''
  const [text, setText] = useState(initial)
  const [resolution, setResolution] = useState<ResolutionStatus | ''>('')
  const [approval, setApproval] = useState<ApprovalStatus | ''>('')
  const [request, setRequest] = useState<SearchRequest | null>(
    initial.length >= 2 ? { query: initial, limit: 10, filters: {} } : null,
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const search = useKnowledgeSearch(request)

  const run = (query: string) => {
    const trimmed = query.trim()
    if (trimmed.length < 2) return
    setText(trimmed)
    setSelectedId(null)
    setParams({ q: trimmed }, { replace: true })
    setRequest({
      query: trimmed,
      limit: 10,
      filters: {
        resolution_status: resolution || null,
        approval_status: approval || null,
      },
    })
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    run(text)
  }

  const data = search.data
  const results = data?.results ?? []
  const selected = results.find((r) => r.id === selectedId) ?? results[0] ?? null
  const note = data ? semanticNotes[data.retrieval.semantic] : null

  return (
    <div className="flex flex-col gap-6">
      <PageHeader description="Describe the problem in your own words. Matches by meaning, keywords and exact identifiers (equipment, sites, incidents), with the original messages behind every answer." />
      <Card>
        <CardContent className="flex flex-col gap-4">
          <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row" role="search">
            <label htmlFor="knowledge-search" className="sr-only">
              Describe the problem
            </label>
            <div className="relative flex-1">
              <SearchIcon
                className="pointer-events-none absolute top-1/2 left-3.5 size-5 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <input
                id="knowledge-search"
                type="search"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="e.g. customers keep losing their connection even after a router reboot"
                maxLength={500}
                autoComplete="off"
                className="h-12 w-full rounded-lg border bg-background pr-3 pl-11 text-base text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              />
            </div>
            <Button
              type="submit"
              size="lg"
              className="h-12 px-6"
              disabled={text.trim().length < 2 || search.isFetching}
            >
              {search.isFetching ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <SearchIcon aria-hidden="true" />
              )}
              Search
            </Button>
          </form>

          <div className="flex flex-wrap items-center gap-3 text-sm">
            <FilterSelect
              label="Resolution"
              value={resolution}
              onChange={(v) => setResolution(v as ResolutionStatus | '')}
              options={[
                ['', 'Any'],
                ['confirmed_in_conversation', 'Confirmed in conversation'],
                ['suggested', 'Suggested'],
                ['unknown', 'Unknown'],
              ]}
            />
            <FilterSelect
              label="Expert review"
              value={approval}
              onChange={(v) => setApproval(v as ApprovalStatus | '')}
              options={[
                ['', 'Any'],
                ['unreviewed', 'Unreviewed'],
                ['approved', 'Approved'],
                ['rejected', 'Rejected'],
              ]}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Try:</span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => run(example)}
                className="rounded-full border bg-muted/40 px-3 py-1 text-xs text-foreground transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {example}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {search.isError && <Notice tone="error">{getErrorMessage(search.error)}</Notice>}
      {note && <Notice tone="warning">{note}</Notice>}

      {!request && !search.isFetching && (
        <EmptyHint icon={Sparkles}>
          Search the knowledge that Elisa Echo discovered automatically in engineers&apos;
          conversations. Run the simulation on the Live Discovery page first if nothing has been
          discovered yet.
        </EmptyHint>
      )}

      {data && results.length === 0 && !search.isFetching && (
        <EmptyHint icon={CircleDashed}>
          No matching knowledge for “{data.query}”. Try describing the symptoms differently, or
          search for an equipment, site or incident identifier.
        </EmptyHint>
      )}

      {results.length > 0 && (
        <div className={cn('grid gap-6 lg:grid-cols-5', search.isFetching && 'opacity-60')}>
          <div className="flex flex-col gap-3 lg:col-span-2">
            <p className="text-sm text-muted-foreground">
              {results.length} result{results.length === 1 ? '' : 's'} for “{data?.query}”
              {data?.retrieval.semantic === 'used' && ' · meaning + keywords + identifiers'}
            </p>
            {results.map((result, index) => (
              <ResultCard
                key={result.id}
                result={result}
                position={index + 1}
                selected={result.id === selected?.id}
                onSelect={() => setSelectedId(result.id)}
              />
            ))}
            <p className="text-xs text-muted-foreground">{data?.access_note}</p>
          </div>
          <div className="lg:col-span-3">{selected && <ResultDetail result={selected} />}</div>
        </div>
      )}
    </div>
  )
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: [string, string][]
}) {
  return (
    <label className="flex items-center gap-2 text-muted-foreground">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded-md border bg-background px-2 text-sm text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
      >
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  )
}

function ResolutionBadge({ status }: { status: ResolutionStatus }) {
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

function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  return (
    <Badge variant="outline">
      {status === 'approved'
        ? 'Expert-approved'
        : status === 'rejected'
          ? 'Rejected by expert'
          : 'Not expert-reviewed'}
    </Badge>
  )
}

function relevance(ranking: SearchRanking): string[] {
  const parts: string[] = []
  if (ranking.semantic_similarity !== null) {
    parts.push(`Similar meaning (${Math.round(ranking.semantic_similarity * 100)}%)`)
  }
  if (ranking.keyword_rank !== null) parts.push('Shared keywords')
  if (ranking.matched_identifiers.length > 0) parts.push('Exact identifier match')
  return parts
}

function ResultCard({
  result,
  position,
  selected,
  onSelect,
}: {
  result: SearchResult
  position: number
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex flex-col gap-2 rounded-xl border bg-card p-4 text-left transition-colors',
        'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
        selected ? 'border-primary/50 ring-1 ring-primary/30' : 'hover:bg-muted/40',
      )}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
          {position}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-foreground">{result.title}</p>
          <p className="mt-0.5 line-clamp-2 text-sm text-muted-foreground">
            {result.problem_description}
          </p>
        </div>
      </div>
      {result.symptoms.length > 0 && (
        <p className="line-clamp-1 text-xs text-muted-foreground">
          Symptoms: {result.symptoms.slice(0, 2).join('; ')}
        </p>
      )}
      {result.resolution && (
        <p className="line-clamp-2 text-sm text-foreground">
          <span className="font-medium">Fix: </span>
          {result.resolution}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-1.5">
        <ResolutionBadge status={result.resolution_status} />
        <ApprovalBadge status={result.approval_status} />
        {[...result.equipment_identifiers, ...result.incident_numbers].map((id) => (
          <Badge key={id} variant="secondary" className="font-mono">
            {id}
          </Badge>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <MessageSquareQuote className="size-3.5" aria-hidden="true" />
          {result.evidence_status === 'missing'
            ? 'No supporting messages'
            : `${result.evidence.length} supporting message${result.evidence.length === 1 ? '' : 's'}`}
        </span>
        <span>{relevance(result.ranking).join(' · ')}</span>
      </div>
    </button>
  )
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

function ResultDetail({ result }: { result: SearchResult }) {
  const confirmed = result.resolution_status === 'confirmed_in_conversation'
  const position = new Map(result.evidence.map((e, i) => [e.message_id, i + 1]))

  return (
    <Card className="lg:sticky lg:top-20">
      <CardHeader>
        <CardTitle className="text-lg">{result.title}</CardTitle>
        <CardDescription className="flex flex-wrap items-center gap-1.5 pt-1">
          <ResolutionBadge status={result.resolution_status} />
          <ApprovalBadge status={result.approval_status} />
          <span className="text-xs">Updated {formatTime(result.updated_at)}</span>
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" asChild>
            <Link to={`/troubleshoot?problem=${encodeURIComponent(result.problem_description)}`}>
              <Workflow aria-hidden="true" />
              Build a troubleshooting guide
            </Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to={`/knowledge?item=${result.id}`}>Open in Knowledge Base</Link>
          </Button>
        </div>
        {result.approval_status !== 'approved' && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>
              {confirmed
                ? 'Engineers reported in chat that this fix worked. It has not been reviewed or approved as an operational procedure. Check that it applies before using it.'
                : 'This fix was suggested in a conversation but nobody confirmed that it worked.'}
            </span>
          </div>
        )}

        <Section title="Problem">
          <p className="text-sm text-foreground">{result.problem_description}</p>
          {result.symptoms.length > 0 && (
            <ul className="list-disc pl-5 text-sm text-muted-foreground">
              {result.symptoms.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          {result.root_cause && (
            <p className="text-sm text-muted-foreground">Root cause: {result.root_cause}</p>
          )}
        </Section>

        {result.resolution && (
          <Section
            title={confirmed ? 'Resolution (confirmed in conversation)' : 'Suggested resolution'}
          >
            <p className="text-sm font-medium text-foreground">{result.resolution}</p>
          </Section>
        )}

        {result.attempted_actions.length > 0 && (
          <Section title="Troubleshooting history">
            <ol className="flex flex-col gap-2">
              {result.attempted_actions.map((action, i) => (
                <li
                  key={`${action.action}-${i}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-background px-3 py-2"
                >
                  <span className="text-sm text-foreground">{action.action}</span>
                  <span className="flex items-center gap-2">
                    {action.message_ids
                      .filter((id) => position.has(id))
                      .map((id) => (
                        <a
                          key={id}
                          href={`#evidence-${id}`}
                          className="rounded border bg-muted px-1.5 font-mono text-xs text-muted-foreground hover:text-foreground"
                        >
                          #{position.get(id)}
                        </a>
                      ))}
                    <Badge variant={action.outcome === 'successful' ? 'default' : 'outline'}>
                      {outcomeLabels[action.outcome]}
                    </Badge>
                  </span>
                </li>
              ))}
            </ol>
          </Section>
        )}

        {result.applicability_conditions.length > 0 && (
          <Section title="Applicability and warnings">
            <ul className="list-disc pl-5 text-sm text-foreground">
              {result.applicability_conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </Section>
        )}

        {result.missing_information.length > 0 && (
          <Section title="Missing information">
            <ul className="list-disc pl-5 text-sm text-muted-foreground">
              {result.missing_information.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </Section>
        )}

        <Section title="Original supporting messages">
          {result.evidence_status === 'missing' ? (
            <p className="rounded-lg border border-dashed px-3 py-4 text-sm text-muted-foreground">
              No supporting messages are linked to this knowledge. Treat it with extra caution.
            </p>
          ) : (
            <ol className="flex flex-col gap-3">
              {result.evidence.map((e, i) => (
                <li key={`${e.message_id}-${e.evidence_type}`} id={`evidence-${e.message_id}`}>
                  <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-xs">
                    <span className="font-mono text-muted-foreground">#{i + 1}</span>
                    <span className="font-medium text-foreground">{e.author}</span>
                    <span className="text-muted-foreground">{formatTime(e.sent_at)}</span>
                    <Badge variant="outline">{evidenceLabels[e.evidence_type]}</Badge>
                  </div>
                  <blockquote className="rounded-lg border-l-2 border-primary/40 bg-muted/40 px-3 py-2 text-sm whitespace-pre-wrap text-foreground">
                    {e.deleted_at_source ? (
                      <span className="text-muted-foreground italic">
                        Message deleted at the source; text no longer shown.
                      </span>
                    ) : (
                      e.excerpt
                    )}
                  </blockquote>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {e.source_name ?? 'Unknown source'}
                    {e.thread_title && ` · ${e.thread_title}`}
                    {e.explanation && ` · ${e.explanation}`}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Section>

        <p className="text-xs text-muted-foreground">
          Ranking: {result.ranking.matched_by.join(' + ') || 'n/a'} · fusion score{' '}
          {result.ranking.score.toFixed(4)}
          {result.ranking.matched_identifiers.length > 0 &&
            ` · identifiers ${result.ranking.matched_identifiers.join(', ')}`}
        </p>
      </CardContent>
    </Card>
  )
}

function Notice({ tone, children }: { tone: 'warning' | 'error'; children: ReactNode }) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-2 rounded-lg border px-3 py-2 text-sm',
        tone === 'error'
          ? 'border-red-200 bg-red-50 text-red-800'
          : 'border-amber-200 bg-amber-50 text-amber-900',
      )}
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}

function EmptyHint({ icon: Icon, children }: { icon: typeof Sparkles; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed px-4 py-12 text-center text-sm text-muted-foreground">
      <Icon className="size-6" aria-hidden="true" />
      <p className="max-w-lg">{children}</p>
    </div>
  )
}
