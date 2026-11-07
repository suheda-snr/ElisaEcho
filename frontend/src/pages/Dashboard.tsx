import {
  ArrowRight,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  LoaderCircle,
  Radar,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { resolutionLabels } from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useDiscoveryStatus, useKnowledgeItems } from '@/hooks/useDiscovery'
import { useDatabaseHealth, useHealth } from '@/hooks/useHealth'
import { useKnowledgeGroups } from '@/hooks/useConsolidation'
import { useRecentSessions } from '@/hooks/useTroubleshooting'
import { navItems } from '@/lib/navigation'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { DiscoveryMetrics } from '@/types/api'

export default function Dashboard() {
  const status = useDiscoveryStatus()
  const knowledge = useKnowledgeItems(false)
  const sessions = useRecentSessions()
  const groups = useKnowledgeGroups()
  const metrics = status.data?.metrics ?? null
  const metricsProblem = status.isError ? getErrorMessage(status.error) : status.data?.metrics_error

  const stepValues: Record<string, { value: string; caption: string }> = {
    '/discovery': {
      value: metrics ? String(metrics.messages_processed) : '–',
      caption: 'messages analyzed from chats',
    },
    '/knowledge': {
      value: metrics ? String(metrics.knowledge_items) : '–',
      caption: 'knowledge items with evidence',
    },
    '/network': {
      value: groups.data ? String(groups.data.total) : '–',
      caption: 'groups of related incidents',
    },
    '/search': {
      value: metrics ? String(metrics.confirmed_resolutions) : '–',
      caption: 'confirmed fixes searchable',
    },
    '/troubleshoot': {
      value: sessions.data ? String(sessions.data.total) : '–',
      caption: 'troubleshooting sessions saved',
    },
  }

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Elisa Echo"
        description="Engineers already share how they fix network problems in chat. Elisa Echo finds that knowledge automatically, keeps the messages that prove it, and turns it into searchable fixes and step-by-step guides."
        actions={
          <Button asChild>
            <Link to="/discovery">
              <Radar aria-hidden="true" />
              Start the live demo
            </Link>
          </Button>
        }
      />

      <section aria-labelledby="how-it-works" className="flex flex-col gap-3">
        <h2 id="how-it-works" className="text-sm font-semibold text-foreground">
          How it works
        </h2>
        <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {navItems
            .filter((item) => item.group === 'workflow')
            .map((item) => (
              <li key={item.to}>
                <Link
                  to={item.to}
                  className="group flex h-full flex-col gap-3 rounded-xl border bg-card p-4 transition-shadow hover:shadow-md focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex size-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                      {item.step}
                    </span>
                    <span className="font-medium text-foreground">{item.label}</span>
                    <ArrowRight
                      className="ml-auto size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </div>
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                  <p className="mt-auto flex items-baseline gap-1.5 border-t pt-3">
                    <span className="text-2xl font-semibold text-foreground tabular-nums">
                      {stepValues[item.to]?.value}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {stepValues[item.to]?.caption}
                    </span>
                  </p>
                </Link>
              </li>
            ))}
        </ol>
      </section>

      {metricsProblem && (
        <p className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <CircleAlert className="size-4" aria-hidden="true" />
          Metrics unavailable: {metricsProblem}
        </p>
      )}

      <FeedbackCard metrics={metrics} />

      <div className="grid gap-6 lg:grid-cols-3">
        <OutcomesCard metrics={metrics} loading={status.isPending} className="lg:col-span-2" />
        <SystemStatusCard />
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>Latest discovered knowledge</CardTitle>
            <CardDescription>
              Found automatically in conversations. Not approved until an expert reviews it.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link to="/knowledge">Open Knowledge Base</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {knowledge.isPending ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (knowledge.data?.items.length ?? 0) === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing discovered yet. Run the live demo to see knowledge appear here.
            </p>
          ) : (
            <ul className="flex flex-col divide-y">
              {knowledge.data?.items.slice(0, 5).map((k) => (
                <li key={k.id}>
                  <Link
                    to={`/knowledge?item=${k.id}`}
                    className="flex flex-wrap items-center gap-2 py-2.5 hover:bg-muted/40"
                  >
                    <span className="min-w-0 flex-1 text-sm font-medium text-foreground">
                      {k.title}
                    </span>
                    <Badge
                      variant={
                        k.resolution_status === 'confirmed_in_conversation' ? 'default' : 'outline'
                      }
                    >
                      {resolutionLabels[k.resolution_status]}
                    </Badge>
                    <Badge variant="secondary">
                      {k.approval_status === 'approved' ? 'Expert-approved' : 'Not reviewed'}
                    </Badge>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function OutcomesCard({
  metrics,
  loading,
  className,
}: {
  metrics: DiscoveryMetrics | null
  loading: boolean
  className?: string
}) {
  const rows = metrics
    ? [
        { outcome: 'Confirmed fix', conversations: metrics.confirmed_resolutions },
        { outcome: 'Suggested fix', conversations: metrics.unverified_suggestions },
        {
          outcome: 'Issue, no fix yet',
          conversations: Math.max(0, metrics.candidates_detected - metrics.knowledge_items),
        },
        { outcome: 'Not relevant', conversations: metrics.conversations_ignored },
        { outcome: 'Waiting', conversations: metrics.threads_pending },
        { outcome: 'Failed', conversations: metrics.threads_failed },
      ]
    : []
  const empty = rows.every((r) => r.conversations === 0)

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>What the AI found in conversations</CardTitle>
        <CardDescription>Each analyzed conversation, by outcome</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !metrics ? (
          <p className="text-sm text-muted-foreground">
            Not available without a database connection.
          </p>
        ) : empty ? (
          <p className="flex h-48 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            No conversations yet. Start the live demo.
          </p>
        ) : (
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="outcome"
                  tickLine={false}
                  axisLine={false}
                  interval={0}
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ fill: 'var(--muted)' }}
                  contentStyle={{
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                    background: 'var(--popover)',
                    color: 'var(--popover-foreground)',
                    fontSize: 12,
                  }}
                />
                <Bar
                  dataKey="conversations"
                  name="Conversations"
                  fill="var(--chart-1)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={40}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function StatusRow({
  label,
  ok,
  children,
}: {
  label: string
  ok: boolean | null
  children: ReactNode
}) {
  const Icon = ok === null ? LoaderCircle : ok ? CircleCheck : CircleAlert
  return (
    <li className="flex items-start gap-3 py-2.5">
      <Icon
        className={cn(
          'mt-0.5 size-4 shrink-0',
          ok === null
            ? 'animate-spin text-muted-foreground'
            : ok
              ? 'text-emerald-600'
              : 'text-amber-600',
        )}
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{children}</p>
      </div>
    </li>
  )
}

function SystemStatusCard() {
  const api = useHealth()
  const db = useDatabaseHealth()
  const status = useDiscoveryStatus()
  const analysis = status.data?.analysis
  return (
    <Card>
      <CardHeader>
        <CardTitle>System status</CardTitle>
        <CardDescription>Live checks of each component</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col divide-y">
          <StatusRow label="API" ok={api.isPending ? null : api.isSuccess}>
            {api.isError ? getErrorMessage(api.error) : 'FastAPI backend reachable'}
          </StatusRow>
          <StatusRow label="Database" ok={db.isPending ? null : db.data?.status === 'ok'}>
            {db.data?.status === 'ok'
              ? `Tiger Data PostgreSQL${db.data.pgvector ? ' · pgvector enabled' : ''}`
              : (db.data?.detail ?? 'Unavailable')}
          </StatusRow>
          <StatusRow
            label="AI analysis"
            ok={!analysis ? null : analysis.gemini_configured && !analysis.paused_until}
          >
            {!analysis
              ? 'Checking…'
              : !analysis.gemini_configured
                ? 'Gemini is not configured'
                : analysis.paused_until
                  ? `Paused (quota) until ${new Date(analysis.paused_until).toLocaleTimeString()}`
                  : analysis.model}
          </StatusRow>
          <StatusRow
            label="Semantic search"
            ok={!analysis ? null : Boolean(analysis.embedding_model)}
          >
            {analysis?.embedding_model
              ? `${analysis.embedding_model} · 768 dimensions`
              : 'Not configured'}
          </StatusRow>
        </ul>
        <p className="mt-2 flex items-center gap-1.5 text-xs text-muted-foreground">
          <CircleDashed className="size-3.5" aria-hidden="true" />
          Synthetic demo data only
        </p>
      </CardContent>
    </Card>
  )
}

/** Reuse and real-world feedback, all counted in the database (self-reported outcomes). */
function FeedbackCard({ metrics }: { metrics: DiscoveryMetrics | null }) {
  const tiles: { label: string; value: number | undefined; hint: string }[] = [
    {
      label: 'Knowledge items reused',
      value: metrics?.knowledge_reused,
      hint: 'in followed guides',
    },
    {
      label: 'Sessions completed',
      value: metrics?.sessions_completed,
      hint: 'guided troubleshooting',
    },
    { label: 'Resolved reports', value: metrics?.feedback_resolved, hint: 'self-reported' },
    { label: 'Not resolved reports', value: metrics?.feedback_not_resolved, hint: 'self-reported' },
    {
      label: 'Conflicting feedback',
      value: metrics?.knowledge_with_conflicting_feedback,
      hint: 'items with mixed outcomes',
    },
  ]
  return (
    <section aria-labelledby="feedback-metrics" className="flex flex-col gap-3">
      <h2 id="feedback-metrics" className="text-sm font-semibold text-foreground">
        Real-world validation
      </h2>
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {tiles.map((t) => (
          <div key={t.label} className="flex flex-col gap-0.5 rounded-xl border bg-card px-4 py-3">
            <dt className="text-xs text-muted-foreground">{t.label}</dt>
            <dd className="text-2xl font-semibold text-foreground tabular-nums">
              {t.value ?? '–'}
            </dd>
            <dd className="text-xs text-muted-foreground">{t.hint}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
