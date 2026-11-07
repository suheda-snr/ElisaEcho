import { CircleAlert, CircleCheck, Inbox, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { Panel, PanelHeader } from '@/components/common/Panel'
import { EmptyState, Loading, Notice } from '@/components/common/States'
import {
  EntityChips,
  ResolutionBadge,
  ReviewBadge,
  SourceBadge,
} from '@/components/common/StatusBadges'
import { KnowledgeTypeBadge, OutdatedBadge } from '@/components/context/ContextInfo'
import { formatTime } from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { useDiscoveryStatus, useKnowledgeItems } from '@/hooks/useDiscovery'
import { useSlackStatus } from '@/hooks/useIntegrations'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { DiscoveryMetrics } from '@/types/api'

export default function Dashboard() {
  const status = useDiscoveryStatus()
  const knowledge = useKnowledgeItems(false)
  const metrics = status.data?.metrics ?? null
  const metricsProblem = status.isError ? getErrorMessage(status.error) : status.data?.metrics_error
  const recent = knowledge.data?.items.slice(0, 7) ?? []

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        actions={
          <Button asChild>
            <Link to="/knowledge">Search knowledge</Link>
          </Button>
        }
      />

      {metricsProblem && <Notice tone="warning">Metrics unavailable: {metricsProblem}</Notice>}

      <Panel as="div" className="grid grid-cols-2 divide-border lg:grid-cols-4 lg:divide-x">
        <Stat
          label="Conversations analyzed"
          value={metrics?.threads_analyzed}
          note={metrics && `of ${metrics.threads_total} received`}
        />
        <Stat
          label="Knowledge discovered"
          value={metrics?.knowledge_items}
          note={metrics && `${metrics.confirmed_resolutions} confirmed in chat`}
        />
        <Stat
          label="Linked network entities"
          value={metrics?.linked_entities}
          note="Nodes, sites, unit classes and events"
        />
        <Stat
          label="Needs expert review"
          value={metrics?.needs_review}
          note="Not yet approved"
          attention={Boolean(metrics?.needs_review)}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Panel>
          <PanelHeader
            title="Recent discoveries"
            actions={
              <Link
                to="/knowledge?tab=all"
                className="text-sm font-medium text-primary hover:underline"
              >
                View all
              </Link>
            }
          />
          {knowledge.isPending ? (
            <div className="px-4">
              <Loading />
            </div>
          ) : recent.length === 0 ? (
            <div className="p-4">
              <EmptyState
                icon={Inbox}
                title="Nothing discovered yet"
                action={
                  <Button asChild>
                    <Link to="/discovery">Open Live Discovery</Link>
                  </Button>
                }
              >
                Knowledge appears here as soon as a connected conversation contains a fix or
                operational context.
              </EmptyState>
            </div>
          ) : (
            <ul className="divide-y">
              {recent.map((k) => (
                <li key={k.id}>
                  <Link
                    to={`/knowledge?item=${k.id}`}
                    className="grid gap-x-6 gap-y-2 px-4 py-3.5 transition-colors duration-150 hover:bg-muted/50 focus-visible:bg-muted/50 focus-visible:outline-none sm:grid-cols-[minmax(0,1fr)_auto]"
                  >
                    <span className="flex min-w-0 flex-col gap-1.5">
                      <span
                        className="truncate text-sm font-medium text-foreground"
                        title={k.title}
                      >
                        {k.title}
                      </span>
                      <EntityChips links={k.entity_links} max={3} />
                    </span>
                    <span className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end sm:justify-center">
                      <span className="flex flex-wrap items-center gap-1.5">
                        <OutdatedBadge validTo={k.valid_to} />
                        <KnowledgeTypeBadge type={k.knowledge_type} />
                        {k.approval_status !== 'unreviewed' && (
                          <ReviewBadge status={k.approval_status} />
                        )}
                        <ResolutionBadge status={k.resolution_status} />
                      </span>
                      <span className="flex items-center gap-3">
                        <SourceBadge type={k.source_type} />
                        <span className="text-xs text-muted-foreground tabular-nums">
                          {formatTime(k.created_at)}
                        </span>
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <SystemPanel metrics={metrics} />
      </div>
    </div>
  )
}

function Stat({
  label,
  value,
  note,
  attention,
}: {
  label: string
  value: number | undefined
  note?: string | null | false
  attention?: boolean
}) {
  return (
    <div className="flex flex-col gap-1 border-b px-5 py-4 last:border-b-0 lg:border-b-0 [&:nth-child(-n+2)]:border-b lg:[&:nth-child(-n+2)]:border-b-0">
      <span className="text-[13px] text-muted-foreground">{label}</span>
      <span className="flex items-center gap-2">
        <span className="text-[28px] leading-none font-semibold tracking-tight text-foreground tabular-nums">
          {value ?? '–'}
        </span>
        {attention && (
          <span className="size-2 rounded-full bg-amber-500" aria-label="Needs attention" />
        )}
      </span>
      {note && <span className="text-xs text-muted-foreground">{note}</span>}
    </div>
  )
}

function Row({
  ok,
  busy,
  label,
  children,
}: {
  ok: boolean
  busy?: boolean
  label: string
  children: ReactNode
}) {
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      {busy ? (
        <LoaderCircle
          className="mt-0.5 size-4 shrink-0 animate-spin text-primary"
          aria-hidden="true"
        />
      ) : ok ? (
        <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
      ) : (
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />
      )}
      <span className="min-w-0">
        <span className="block text-sm font-medium text-foreground">{label}</span>
        <span className="block text-[13px] text-muted-foreground">{children}</span>
      </span>
    </li>
  )
}

function SystemPanel({ metrics }: { metrics: DiscoveryMetrics | null }) {
  const status = useDiscoveryStatus()
  const slack = useSlackStatus()
  const analysis = status.data?.analysis
  const busy = (analysis?.analyzing ?? 0) + (analysis?.queued ?? 0)
  const reuse: [string, number | undefined][] = [
    ['Knowledge reused in guides', metrics?.knowledge_reused],
    ['Sessions completed', metrics?.sessions_completed],
    ['Reported as working', metrics?.feedback_resolved],
    ['Reported as not working', metrics?.feedback_not_resolved],
  ]
  return (
    <Panel as="aside" className="self-start">
      <PanelHeader
        title="Capture"
        actions={
          <Link to="/discovery" className="text-sm font-medium text-primary hover:underline">
            Live view
          </Link>
        }
      />
      <ul className="divide-y">
        <Row ok={Boolean(slack.data?.connected)} label="Slack">
          {slack.data?.connected
            ? `${slack.data.workspace_name ?? 'Connected'}, ${slack.data.monitored_channels.length} channel${slack.data.monitored_channels.length === 1 ? '' : 's'}`
            : 'Not connected'}
        </Row>
        <Row
          ok={Boolean(analysis?.gemini_configured) && !analysis?.paused_until}
          busy={busy > 0}
          label="AI analysis"
        >
          {!analysis
            ? 'Checking…'
            : !analysis.gemini_configured
              ? 'Not configured'
              : analysis.paused_until
                ? `Paused until ${formatTime(analysis.paused_until)} (quota)`
                : busy > 0
                  ? `Analyzing ${busy} conversation${busy === 1 ? '' : 's'}`
                  : 'Idle, waiting for new messages'}
        </Row>
        <Row ok={!metrics?.threads_failed} label="Pipeline">
          {metrics
            ? `${metrics.threads_pending} waiting, ${metrics.threads_failed} failed, ${metrics.conversations_ignored} not relevant`
            : 'Checking…'}
        </Row>
      </ul>
      <div className="border-t px-4 pt-3 pb-4">
        <h3 className="text-sm font-semibold text-foreground">Reuse and feedback</h3>
        <dl className="mt-2 flex flex-col">
          {reuse.map(([label, value]) => (
            <div key={label} className="flex items-baseline justify-between gap-3 py-1 text-[13px]">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className={cn('font-semibold tabular-nums text-foreground')}>{value ?? '–'}</dd>
            </div>
          ))}
        </dl>
        {Boolean(metrics?.knowledge_with_conflicting_feedback) && (
          <p className="mt-2 flex items-center gap-1.5 text-[13px] text-amber-800">
            <CircleAlert className="size-3.5" aria-hidden="true" />
            {metrics?.knowledge_with_conflicting_feedback} item(s) with conflicting outcomes
          </p>
        )}
        <p className="mt-2 text-xs text-muted-foreground">
          Outcomes are self-reported by engineers.
        </p>
      </div>
    </Panel>
  )
}
