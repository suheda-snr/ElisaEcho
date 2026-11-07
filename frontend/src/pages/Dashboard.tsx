import {
  ArrowRight,
  BookOpenText,
  CircleAlert,
  CircleCheck,
  Hash,
  Inbox,
  MessagesSquare,
  Network,
  ShieldQuestion,
  Sparkles,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import {
  EntityChips,
  ResolutionBadge,
  ReviewBadge,
  SourceBadge,
} from '@/components/common/StatusBadges'
import { EmptyState, Loading, Notice } from '@/components/common/States'
import { KnowledgeTypeBadge, OutdatedBadge } from '@/components/context/ContextInfo'
import { formatTime } from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  const recent = knowledge.data?.items.slice(0, 6) ?? []

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        actions={
          <Button variant="outline" asChild>
            <Link to="/knowledge">
              <BookOpenText aria-hidden="true" />
              Knowledge Explorer
            </Link>
          </Button>
        }
      />

      {metricsProblem && <Notice tone="warning">Metrics unavailable: {metricsProblem}</Notice>}

      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          icon={MessagesSquare}
          label="Conversations analyzed"
          value={metrics?.threads_analyzed}
          detail={metrics ? `of ${metrics.threads_total} received` : undefined}
        />
        <Metric
          icon={Sparkles}
          label="Knowledge discovered"
          value={metrics?.knowledge_items}
          detail={metrics ? `${metrics.confirmed_resolutions} confirmed in chat` : undefined}
        />
        <Metric
          icon={Network}
          label="Linked network entities"
          value={metrics?.linked_entities}
          detail="nodes, sites, unit classes, events"
        />
        <Metric
          icon={ShieldQuestion}
          label="Needs expert review"
          value={metrics?.needs_review}
          detail="not yet approved"
          highlight={Boolean(metrics?.needs_review)}
        />
      </dl>

      <div className="grid gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle>Recent discoveries</CardTitle>
            <Link
              to="/knowledge?tab=all"
              className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              View all
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </CardHeader>
          <CardContent>
            {knowledge.isPending ? (
              <Loading />
            ) : recent.length === 0 ? (
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
            ) : (
              <ul className="-my-1 divide-y">
                {recent.map((k) => (
                  <li key={k.id}>
                    <Link
                      to={`/knowledge?item=${k.id}`}
                      className="flex flex-col gap-1.5 rounded-lg px-2 py-3 hover:bg-muted/50 focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                    >
                      <span className="flex flex-wrap items-start justify-between gap-2">
                        <span className="font-medium text-foreground">{k.title}</span>
                        <span className="flex shrink-0 items-center gap-1.5">
                          <OutdatedBadge validTo={k.valid_to} />
                          <KnowledgeTypeBadge type={k.knowledge_type} />
                          <ResolutionBadge status={k.resolution_status} />
                        </span>
                      </span>
                      <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                        <EntityChips links={k.entity_links} max={3} />
                        <SourceBadge type={k.source_type} />
                        <span className="text-xs text-muted-foreground">
                          {formatTime(k.created_at)}
                        </span>
                        {k.approval_status !== 'unreviewed' && (
                          <ReviewBadge status={k.approval_status} />
                        )}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="flex flex-col gap-6 lg:col-span-4">
          <CaptureStatus />
          <ReuseCard metrics={metrics} />
        </div>
      </div>
    </div>
  )
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
  highlight,
}: {
  icon: typeof Sparkles
  label: string
  value: number | undefined
  detail?: string
  highlight?: boolean
}) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border bg-card px-4 py-3.5">
      <dt className="flex items-center gap-2 text-sm text-muted-foreground">
        <Icon className="size-4" aria-hidden="true" />
        {label}
      </dt>
      <dd
        className={cn(
          'text-3xl font-semibold tracking-tight tabular-nums',
          highlight ? 'text-amber-700' : 'text-foreground',
        )}
      >
        {value ?? '–'}
      </dd>
      {detail && <dd className="text-xs text-muted-foreground">{detail}</dd>}
    </div>
  )
}

function StatusRow({ ok, label, children }: { ok: boolean; label: string; children: ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 py-2">
      {ok ? (
        <CircleCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden="true" />
      ) : (
        <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />
      )}
      <span className="min-w-0">
        <span className="block text-sm font-medium text-foreground">{label}</span>
        <span className="block text-sm text-muted-foreground">{children}</span>
      </span>
    </li>
  )
}

function CaptureStatus() {
  const status = useDiscoveryStatus()
  const slack = useSlackStatus()
  const analysis = status.data?.analysis
  const metrics = status.data?.metrics
  const busy = (analysis?.analyzing ?? 0) + (analysis?.queued ?? 0)
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>Capture</CardTitle>
        <Link to="/discovery" className="text-sm font-medium text-primary hover:underline">
          Live view
        </Link>
      </CardHeader>
      <CardContent>
        <ul className="-my-2 divide-y">
          <StatusRow ok={Boolean(slack.data?.connected)} label="Slack">
            <span className="inline-flex items-center gap-1">
              <Hash className="size-3.5" aria-hidden="true" />
              {slack.data?.connected
                ? `${slack.data.workspace_name ?? 'Connected'} · ${slack.data.monitored_channels.length} channel(s)`
                : 'Not connected'}
            </span>
          </StatusRow>
          <StatusRow
            ok={Boolean(analysis?.gemini_configured) && !analysis?.paused_until}
            label="AI analysis"
          >
            {!analysis
              ? '–'
              : !analysis.gemini_configured
                ? 'Gemini is not configured'
                : analysis.paused_until
                  ? `Paused until ${formatTime(analysis.paused_until)} (quota)`
                  : busy > 0
                    ? `Analyzing ${busy} conversation(s)`
                    : 'Idle, waiting for new messages'}
          </StatusRow>
          <StatusRow ok={!metrics?.threads_failed} label="Pipeline">
            {metrics
              ? `${metrics.threads_pending} waiting · ${metrics.threads_failed} failed · ${metrics.conversations_ignored} not relevant`
              : '–'}
          </StatusRow>
        </ul>
      </CardContent>
    </Card>
  )
}

function ReuseCard({ metrics }: { metrics: DiscoveryMetrics | null }) {
  const rows: [string, number | undefined][] = [
    ['Knowledge reused in guides', metrics?.knowledge_reused],
    ['Troubleshooting sessions completed', metrics?.sessions_completed],
    ['Reported as working', metrics?.feedback_resolved],
    ['Reported as not working', metrics?.feedback_not_resolved],
  ]
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reuse and feedback</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <dl className="flex flex-col gap-1.5">
          {rows.map(([label, value]) => (
            <div key={label} className="flex items-baseline justify-between gap-3 text-sm">
              <dt className="text-muted-foreground">{label}</dt>
              <dd className="font-semibold text-foreground tabular-nums">{value ?? '–'}</dd>
            </div>
          ))}
        </dl>
        {Boolean(metrics?.knowledge_with_conflicting_feedback) && (
          <Notice tone="warning">
            {metrics?.knowledge_with_conflicting_feedback} item(s) with conflicting outcomes
          </Notice>
        )}
        <p className="text-xs text-muted-foreground">Outcomes are self-reported by engineers.</p>
      </CardContent>
    </Card>
  )
}
