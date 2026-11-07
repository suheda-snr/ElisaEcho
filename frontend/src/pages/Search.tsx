import {
  ArrowRight,
  History,
  LoaderCircle,
  MessageSquareQuote,
  Network,
  Search as SearchIcon,
  SearchX,
  SlidersHorizontal,
  Users,
  Workflow,
} from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import {
  EntityChips,
  ResolutionBadge,
  ReviewBadge,
  SourceBadge,
} from '@/components/common/StatusBadges'
import { EmptyState, Notice, SectionTitle } from '@/components/common/States'
import { groupHeadline } from '@/components/consolidation/labels'
import { KnowledgeTypeBadge, OutdatedBadge } from '@/components/context/ContextInfo'
import { evidenceLabels, formatTime } from '@/components/discovery/labels'
import { feedbackSentence } from '@/components/feedback/labels'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useKnowledgeSearch } from '@/hooks/useSearch'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type {
  ApprovalStatus,
  EvidenceType,
  GroupBrief,
  ResolutionStatus,
  SearchRequest,
  SearchResponse,
  SearchResult,
} from '@/types/api'

// Queries that fit the demo data; they run against the real search API.
const EXAMPLES = [
  'TRN-118: port up after optical module swap, but zero traffic',
  'Customers lose their connection every half hour',
  'How do I get the barrier key for SITE-PELLO-03?',
  'BGP session keeps resetting',
]

const semanticNotes: Record<SearchResponse['retrieval']['semantic'], string | null> = {
  used: null,
  no_embeddings: 'Nothing is embedded yet: keyword and identifier matching only.',
  unavailable: 'Semantic search is temporarily unavailable: keyword and identifier matching only.',
  not_configured: 'Gemini is not configured: keyword and identifier matching only.',
}

const selectClass =
  'h-9 rounded-lg border bg-background px-2 text-sm text-foreground focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none'

export default function Search() {
  // The query lives in the URL (?q=...), so searches can be shared and survive reloads.
  const [params, setParams] = useSearchParams()
  const initial = params.get('q')?.trim() ?? ''
  const [text, setText] = useState(initial)
  const [showFilters, setShowFilters] = useState(false)
  const [resolution, setResolution] = useState<ResolutionStatus | ''>('')
  const [approval, setApproval] = useState<ApprovalStatus | ''>('')
  const [includeOutdated, setIncludeOutdated] = useState(false)
  const [asOf, setAsOf] = useState('')
  const [request, setRequest] = useState<SearchRequest | null>(
    initial.length >= 2 ? { query: initial, limit: 10, filters: {} } : null,
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const search = useKnowledgeSearch(request)
  const activeFilters = [resolution, approval, includeOutdated, asOf].filter(Boolean).length

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
        include_outdated: includeOutdated,
        as_of: asOf ? new Date(`${asOf}T12:00:00Z`).toISOString() : null,
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
    <div className="flex flex-col gap-5">
      <form onSubmit={onSubmit} className="flex flex-col gap-3" role="search">
        <div className="flex flex-col gap-2 sm:flex-row">
          <label htmlFor="knowledge-search" className="sr-only">
            Describe the problem
          </label>
          <div className="relative flex-1">
            <SearchIcon
              className="pointer-events-none absolute top-1/2 left-4 size-5 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <input
              id="knowledge-search"
              type="search"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Describe the problem, or type a node, site or incident ID"
              maxLength={500}
              autoComplete="off"
              className="h-13 w-full rounded-xl border bg-background pr-4 pl-12 text-base text-foreground shadow-xs placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            />
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="h-13"
              onClick={() => setShowFilters((v) => !v)}
              aria-expanded={showFilters}
            >
              <SlidersHorizontal aria-hidden="true" />
              Filters
              {activeFilters > 0 && (
                <span className="rounded-full bg-primary px-1.5 text-xs text-primary-foreground">
                  {activeFilters}
                </span>
              )}
            </Button>
            <Button
              type="submit"
              size="lg"
              className="h-13 flex-1 px-6 sm:flex-none"
              disabled={text.trim().length < 2 || search.isFetching}
            >
              {search.isFetching ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <SearchIcon aria-hidden="true" />
              )}
              Search
            </Button>
          </div>
        </div>

        {showFilters && (
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3 rounded-xl border bg-background px-4 py-3 text-sm">
            <label className="flex items-center gap-2 text-muted-foreground">
              Resolution
              <select
                value={resolution}
                onChange={(e) => setResolution(e.target.value as ResolutionStatus | '')}
                className={selectClass}
              >
                <option value="">Any</option>
                <option value="confirmed_in_conversation">Confirmed in chat</option>
                <option value="suggested">Suggested</option>
                <option value="unknown">Unclear</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-muted-foreground">
              Review
              <select
                value={approval}
                onChange={(e) => setApproval(e.target.value as ApprovalStatus | '')}
                className={selectClass}
              >
                <option value="">Any</option>
                <option value="unreviewed">Needs review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-muted-foreground">
              Valid on
              <input
                type="date"
                value={asOf}
                onChange={(e) => setAsOf(e.target.value)}
                className={selectClass}
                aria-label="Show knowledge that was valid on this date"
              />
            </label>
            <label className="flex items-center gap-2 text-muted-foreground">
              <input
                type="checkbox"
                checked={includeOutdated}
                onChange={(e) => setIncludeOutdated(e.target.checked)}
                className="size-4 accent-primary"
              />
              Include outdated
            </label>
            <span className="text-xs text-muted-foreground">Applied on the next search.</span>
          </div>
        )}

        {!data && !search.isFetching && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">Try</span>
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => run(example)}
                className="rounded-full border bg-background px-3 py-1 text-sm text-foreground transition-colors hover:bg-accent focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              >
                {example}
              </button>
            ))}
          </div>
        )}
      </form>

      {search.isError && <Notice tone="error">{getErrorMessage(search.error)}</Notice>}
      {note && <Notice tone="warning">{note}</Notice>}

      {data && results.length === 0 && !search.isFetching && (
        <EmptyState icon={SearchX} title={`Nothing found for “${data.query}”`}>
          Describe the symptoms differently, or search for a node, site or incident ID.
        </EmptyState>
      )}

      {results.length > 0 && (
        <div className={cn('grid gap-5 lg:grid-cols-12', search.isFetching && 'opacity-60')}>
          <div className="flex flex-col gap-2 lg:col-span-5">
            <p className="text-sm text-muted-foreground">
              {results.length} result{results.length === 1 ? '' : 's'}
            </p>
            {data?.related_groups.map((g) => (
              <Link
                key={g.id}
                to={`/knowledge?group=${g.id}`}
                className="flex items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-950 hover:bg-sky-100"
              >
                <Network className="size-4 shrink-0" aria-hidden="true" />
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{groupHeadline(g)}</span>
                  {g.conflict_count > 0 && ', with conflicting reports'}
                </span>
                <ArrowRight className="size-4 shrink-0" aria-hidden="true" />
              </Link>
            ))}
            <ul className="flex flex-col gap-2" aria-label="Search results">
              {results.map((result) => (
                <li key={result.id}>
                  <ResultRow
                    result={result}
                    group={data?.related_groups.find((g) => g.id === result.group_id)}
                    selected={result.id === selected?.id}
                    onSelect={() => setSelectedId(result.id)}
                  />
                </li>
              ))}
            </ul>
          </div>
          <div className="lg:col-span-7">{selected && <ResultPanel result={selected} />}</div>
        </div>
      )}
    </div>
  )
}

function ResultRow({
  result,
  group,
  selected,
  onSelect,
}: {
  result: SearchResult
  group?: GroupBrief
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cn(
        'flex w-full flex-col gap-1.5 rounded-xl border bg-card px-4 py-3 text-left transition-colors',
        'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
        selected ? 'border-primary/60 ring-1 ring-primary/30' : 'hover:bg-muted/40',
      )}
    >
      <span className="flex items-start justify-between gap-2">
        <span className="font-medium text-foreground">{result.title}</span>
        <span className="flex shrink-0 gap-1">
          <OutdatedBadge validTo={result.valid_to} />
          <KnowledgeTypeBadge type={result.knowledge_type} />
        </span>
      </span>
      {result.resolution && (
        <span className="line-clamp-2 text-sm text-foreground/80">{result.resolution}</span>
      )}
      <EntityChips links={result.entity_links} max={3} />
      <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <ResolutionBadge status={result.resolution_status} />
        <ReviewBadge status={result.approval_status} />
        <span className="inline-flex items-center gap-1">
          <MessageSquareQuote className="size-3.5" aria-hidden="true" />
          {uniqueMessages(result).length} message{uniqueMessages(result).length === 1 ? '' : 's'}
        </span>
        {result.feedback && result.feedback.sessions > 0 && (
          <span
            className={cn(
              'inline-flex items-center gap-1',
              result.feedback.has_conflicting_reports ? 'text-amber-800' : 'text-emerald-800',
            )}
          >
            <Users className="size-3.5" aria-hidden="true" />
            {result.feedback.counts.resolved} worked · {result.feedback.counts.not_resolved} did not
          </span>
        )}
        {group && <span className="text-sky-800">{group.case_count} related cases</span>}
      </span>
    </button>
  )
}

function ResultPanel({ result }: { result: SearchResult }) {
  const messages = uniqueMessages(result)
  const evidence = messages.filter((m) => !m.deleted_at_source).slice(0, 3)
  const problemParam = encodeURIComponent(result.problem_description)
  return (
    <Card className="lg:sticky lg:top-24">
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <OutdatedBadge validTo={result.valid_to} />
            <KnowledgeTypeBadge type={result.knowledge_type} />
            <ResolutionBadge status={result.resolution_status} />
            <ReviewBadge status={result.approval_status} />
          </div>
          <h2 className="text-xl font-semibold text-foreground">{result.title}</h2>
          <EntityChips links={result.entity_links} max={6} />
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link to={`/troubleshoot?problem=${problemParam}`}>
                <Workflow aria-hidden="true" />
                Start troubleshooting
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to={`/knowledge?item=${result.id}`}>
                View details
                <ArrowRight aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </div>

        {result.superseded_by && (
          <Notice tone="warning">
            Outdated since {formatTime(result.valid_to)}. Replaced by{' '}
            <Link
              to={`/knowledge?item=${result.superseded_by.id}`}
              className="font-medium underline"
            >
              {result.superseded_by.title}
            </Link>
            .
          </Notice>
        )}

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <SectionTitle>Problem</SectionTitle>
            <p className="text-sm text-foreground">{result.problem_description}</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <SectionTitle>
              {result.resolution_status === 'confirmed_in_conversation'
                ? 'Fix (confirmed in chat)'
                : 'Suggested fix'}
            </SectionTitle>
            <p className="text-sm font-medium text-foreground">
              {result.resolution ?? 'No fix recorded'}
            </p>
            {result.applicability_conditions.slice(0, 2).map((c) => (
              <p key={c} className="text-sm text-muted-foreground">
                · {c}
              </p>
            ))}
          </div>
        </div>

        {result.feedback && result.feedback.sessions > 0 && (
          <div className="flex flex-col gap-1.5">
            <SectionTitle>Used since (self-reported)</SectionTitle>
            <p className="text-sm text-foreground">{feedbackSentence(result.feedback)}</p>
            {result.feedback.condition_notes.length > 0 && (
              <p className="text-sm text-amber-900">
                Differs by condition: {result.feedback.condition_notes.join('; ')}
              </p>
            )}
          </div>
        )}

        <div className="flex flex-col gap-2">
          <SectionTitle>
            Evidence ({messages.length} message{messages.length === 1 ? '' : 's'})
          </SectionTitle>
          {evidence.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No supporting messages. Use with caution.
            </p>
          ) : (
            <ol className="flex flex-col gap-2">
              {evidence.map((e) => (
                <li key={e.message_id} className="rounded-lg bg-muted/50 px-3 py-2">
                  <p className="mb-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{e.author}</span>
                    <SourceBadge type={e.source_type} />
                    <span>{formatTime(e.sent_at)}</span>
                    <span>· {e.roles.map((r) => evidenceLabels[r]).join(', ')}</span>
                  </p>
                  <p className="line-clamp-3 text-sm whitespace-pre-wrap text-foreground">
                    {e.excerpt}
                  </p>
                </li>
              ))}
            </ol>
          )}
          {messages.length > evidence.length && (
            <Link
              to={`/knowledge?item=${result.id}`}
              className="text-sm font-medium text-primary hover:underline"
            >
              All evidence and details
            </Link>
          )}
        </div>

        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <History className="size-3.5 shrink-0" aria-hidden="true" />
          Valid from {result.valid_from ? formatTime(result.valid_from) : 'unknown'}
          {result.valid_to ? ` until ${formatTime(result.valid_to)}` : ', still believed true'} ·
          matched by {result.ranking.matched_by.join(', ') || 'n/a'}
          {result.ranking.matched_identifiers.length > 0 &&
            ` (${result.ranking.matched_identifiers.join(', ')})`}
        </p>
      </CardContent>
    </Card>
  )
}

/** Evidence grouped by message: one entry per message with all the roles it was cited for. */
function uniqueMessages(result: SearchResult) {
  const byId = new Map<string, SearchResult['evidence'][number] & { roles: EvidenceType[] }>()
  for (const e of result.evidence) {
    const existing = byId.get(e.message_id)
    if (existing) {
      if (!existing.roles.includes(e.evidence_type)) existing.roles.push(e.evidence_type)
    } else {
      byId.set(e.message_id, { ...e, roles: [e.evidence_type] })
    }
  }
  return [...byId.values()]
}
