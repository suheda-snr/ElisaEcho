import {
  BrainCircuit,
  CircleAlert,
  CircleDashed,
  LoaderCircle,
  RotateCw,
  Workflow,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Disclosure } from '@/components/common/Disclosure'
import { Insight } from '@/components/common/Insight'
import { Notice, SectionTitle } from '@/components/common/States'
import { EntityChips, ResolutionBadge, ReviewBadge } from '@/components/common/StatusBadges'
import { OutdatedBadge } from '@/components/context/ContextInfo'
import {
  classificationLabels,
  evidenceLabels,
  formatTime,
  outcomeLabels,
} from '@/components/discovery/labels'
import { Button } from '@/components/ui/button'
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

function MessageRef({ id, messages }: { id: string; messages: Message[] }) {
  const position = messages.findIndex((m) => m.id === id) + 1
  return (
    <a
      href={`#message-${id}`}
      className="shrink-0 rounded bg-muted px-1.5 font-mono text-xs text-muted-foreground hover:text-foreground"
    >
      #{position || '?'}
    </a>
  )
}

function Waiting({ icon: Icon, children }: { icon: typeof BrainCircuit; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border bg-muted/20 px-5 py-7 text-center text-sm leading-relaxed text-muted-foreground">
      <Icon className="size-6 text-muted-foreground/70" aria-hidden="true" />
      <div className="max-w-[26ch]">{children}</div>
    </div>
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
    return <Waiting icon={BrainCircuit}>Select a conversation to see what was discovered.</Waiting>
  }
  const candidate = thread.candidate
  const status = thread.processing_status

  return (
    <div className="flex flex-col gap-4">
      {status === 'processing' && (
        <p className="flex items-center gap-2 text-sm text-primary">
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
          Analyzing the latest messages…
        </p>
      )}

      {status === 'failed' && (
        <Notice tone="warning">
          {candidate
            ? `The latest analysis failed (AI unavailable). Showing the previous result from ${candidate.analyzed_message_count} of ${thread.message_count} messages.`
            : 'The analysis failed (AI unavailable). Nothing was stored.'}
          {onRetry && (
            <span className="mt-2 flex flex-wrap items-center gap-2">
              <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying}>
                <RotateCw className={retrying ? 'animate-spin' : undefined} aria-hidden="true" />
                {retrying ? 'Analyzing…' : 'Retry analysis'}
              </Button>
              {retryError != null && (
                <span className="text-red-700">{getErrorMessage(retryError)}</span>
              )}
            </span>
          )}
        </Notice>
      )}

      {!candidate && status !== 'failed' && (
        <Waiting icon={geminiConfigured ? LoaderCircle : CircleAlert}>
          {geminiConfigured
            ? 'Waiting for the conversation to settle before it is analyzed.'
            : 'AI analysis is not configured, so this conversation cannot be analyzed yet.'}
        </Waiting>
      )}

      {candidate?.detection_status === 'rejected' && (
        <Waiting icon={CircleDashed}>
          <span className="block font-semibold text-foreground">No operational knowledge</span>
          {candidate.summary ?? 'This conversation was ignored.'}
        </Waiting>
      )}

      {candidate?.detection_status === 'incomplete' && (
        <div className="flex flex-col gap-1 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Problem detected, no reusable fix yet</p>
          <p>{candidate.summary}</p>
        </div>
      )}

      {candidate?.knowledge_item_id && (
        <>
          {itemLoading && !item && <p className="text-sm text-muted-foreground">Loading…</p>}
          {Boolean(itemError) && !item && (
            <p className="text-sm text-red-700">{getErrorMessage(itemError)}</p>
          )}
          {item && <Finding item={item} messages={messages} />}
        </>
      )}

      {candidate && (
        <Disclosure title="Processing details">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
            <dt className="text-muted-foreground">Classified as</dt>
            <dd>{classificationLabels[candidate.classification] ?? candidate.classification}</dd>
            <dt className="text-muted-foreground">Analyzed</dt>
            <dd>
              {formatTime(candidate.analyzed_at)} · {candidate.analyzed_message_count} messages
            </dd>
            {item?.discovery?.model_name && (
              <>
                <dt className="text-muted-foreground">Model</dt>
                <dd className="font-mono text-xs">{item.discovery.model_name}</dd>
              </>
            )}
          </dl>
          {candidate.flags.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 text-sm text-amber-900">
              {candidate.flags.map((flag) => (
                <li key={flag}>· {flag}</li>
              ))}
            </ul>
          )}
        </Disclosure>
      )}
    </div>
  )
}

/** The main finding: what, which entity, which action, confirmed?, evidence. */
function Finding({ item, messages }: { item: KnowledgeItemDetail; messages: Message[] }) {
  const missing = item.discovery?.missing_information ?? []
  const evidence = item.evidence.filter(
    (e, i) => item.evidence.findIndex((o) => o.message.id === e.message.id) === i,
  )
  return (
    <>
      <Insight
        label={
          item.knowledge_type === 'site_access' ? 'Site access discovered' : 'Discovered knowledge'
        }
        badges={
          <>
            <ResolutionBadge status={item.resolution_status} />
            <ReviewBadge status={item.approval_status} />
            <OutdatedBadge validTo={item.valid_to} />
          </>
        }
        title={item.title}
      >
        <EntityChips links={item.entity_links} max={5} />
        <div>
          <p className="text-xs font-medium text-insight-foreground">
            {item.knowledge_type === 'site_access' ? 'How to get access' : 'What to do'}
          </p>
          <p className="mt-0.5 text-[15px] leading-relaxed font-medium text-foreground">
            {item.resolution ?? 'No action recorded yet'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 pt-1">
          <Button size="sm" asChild>
            <Link to={`/knowledge?item=${item.id}`}>Open knowledge</Link>
          </Button>
          <Button size="sm" variant="outline" className="bg-card" asChild>
            <Link to={`/troubleshoot?problem=${encodeURIComponent(item.problem_description)}`}>
              <Workflow aria-hidden="true" />
              Troubleshoot
            </Link>
          </Button>
        </div>
      </Insight>

      <div className="flex flex-col gap-2">
        <SectionTitle>Evidence in this conversation</SectionTitle>
        <ul className="flex flex-col gap-2">
          {evidence.map((e) => (
            <li key={e.id} className="flex items-start gap-2.5 text-[13px]">
              <MessageRef id={e.message.id} messages={messages} />
              <span className="min-w-0">
                <span className="font-medium text-foreground">
                  {item.evidence
                    .filter((o) => o.message.id === e.message.id)
                    .map((o) => evidenceLabels[o.evidence_type])
                    .join(', ')}
                </span>
                {e.explanation && (
                  <span className="block text-muted-foreground">{e.explanation}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-col gap-2">
        <Disclosure title="Problem as described">
          <p className="text-sm text-foreground">{item.problem_description}</p>
        </Disclosure>
        {item.attempted_actions.length > 0 && (
          <Disclosure title="What was tried" count={item.attempted_actions.length}>
            <ol className="flex flex-col gap-2">
              {item.attempted_actions.map((a, i) => (
                <li
                  key={`${a.action}-${i}`}
                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                >
                  <span className="text-foreground">{a.action}</span>
                  <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    {a.message_ids.map((id) => (
                      <MessageRef key={id} id={id} messages={messages} />
                    ))}
                    {outcomeLabels[a.outcome]}
                  </span>
                </li>
              ))}
            </ol>
          </Disclosure>
        )}
        {item.applicability_conditions.length > 0 && (
          <Disclosure title="When it applies" count={item.applicability_conditions.length}>
            <ul className="list-disc pl-5 text-sm text-foreground">
              {item.applicability_conditions.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </Disclosure>
        )}
        {missing.length > 0 && (
          <Disclosure title="Missing information" count={missing.length}>
            <ul className="list-disc pl-5 text-sm text-foreground">
              {missing.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </Disclosure>
        )}
      </div>
    </>
  )
}
