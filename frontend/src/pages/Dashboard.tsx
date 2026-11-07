import { ArrowRight, CircleAlert, CircleCheck, LoaderCircle, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useDiscoveryStatus } from '@/hooks/useDiscovery'
import { useHealth } from '@/hooks/useHealth'
import { navItems } from '@/lib/navigation'
import { getErrorMessage } from '@/services/api'
import type { DiscoveryMetrics } from '@/types/api'

function ConnectionCard() {
  const { data, error, isPending, isError, isFetching, refetch } = useHealth()

  return (
    <Card>
      <CardHeader>
        <CardTitle>API connection</CardTitle>
        <CardDescription>Live result of GET /api/health</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {isPending ? (
          <div className="flex items-center gap-3 text-amber-700">
            <LoaderCircle className="size-5 animate-spin" aria-hidden="true" />
            <span className="font-medium">Connecting…</span>
          </div>
        ) : isError ? (
          <div className="flex items-start gap-3 text-red-700">
            <CircleAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">Backend unavailable</p>
              <p className="text-sm text-muted-foreground">{getErrorMessage(error)}</p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-3 text-emerald-700">
            <CircleCheck className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">Backend connected</p>
              <p className="text-sm text-muted-foreground">
                {data.service} reports status “{data.status}”.
              </p>
            </div>
          </div>
        )}
        <div>
          <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
            <RefreshCw className={isFetching ? 'animate-spin' : undefined} aria-hidden="true" />
            Check again
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

const tiles: { key: keyof DiscoveryMetrics; label: string; hint: string }[] = [
  {
    key: 'messages_processed',
    label: 'Messages processed',
    hint: 'Ingested from communication sources',
  },
  { key: 'threads_analyzed', label: 'Threads analyzed', hint: 'Conversations analyzed by Gemini' },
  {
    key: 'candidates_detected',
    label: 'Knowledge candidates',
    hint: 'Conversations with technical knowledge',
  },
  {
    key: 'confirmed_resolutions',
    label: 'Confirmed resolutions',
    hint: 'Fix confirmed in conversation',
  },
  {
    key: 'threads_failed',
    label: 'Processing failures',
    hint: 'Threads whose last analysis failed',
  },
]

function MetricTiles({ metrics }: { metrics: DiscoveryMetrics | null | undefined }) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5">
      {tiles.map((tile) => (
        <Card key={tile.key} size="sm">
          <CardContent>
            <p className="text-xs text-muted-foreground">{tile.label}</p>
            <p className="mt-1 text-2xl font-semibold text-foreground tabular-nums">
              {metrics ? metrics[tile.key].toLocaleString() : '–'}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{tile.hint}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function OutcomesCard({ metrics }: { metrics: DiscoveryMetrics }) {
  const rows = [
    { outcome: 'Confirmed', conversations: metrics.confirmed_resolutions },
    { outcome: 'Suggested', conversations: metrics.unverified_suggestions },
    {
      outcome: 'No fix yet',
      conversations: Math.max(0, metrics.candidates_detected - metrics.knowledge_items),
    },
    { outcome: 'Ignored', conversations: metrics.conversations_ignored },
    { outcome: 'Pending', conversations: metrics.threads_pending },
  ]
  const empty = rows.every((r) => r.conversations === 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Discovery outcomes</CardTitle>
        <CardDescription>Conversations by what the analysis found</CardDescription>
      </CardHeader>
      <CardContent>
        {empty ? (
          <p className="flex h-48 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">
            No conversations yet. Start the simulation on the Live Discovery page.
          </p>
        ) : (
          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="outcome"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
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
                  isAnimationActive={false}
                  name="Conversations"
                  fill="var(--chart-1)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={40}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const status = useDiscoveryStatus()
  const metrics = status.data?.metrics
  const modules = navItems.filter((item) => item.to !== '/')
  const metricsProblem = status.isError ? getErrorMessage(status.error) : status.data?.metrics_error

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">
          Welcome to Elisa Echo
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Operational knowledge discovered automatically from engineers&apos; conversations,
          preserved with the messages that prove it.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-foreground">Knowledge discovery</h2>
        {metricsProblem && (
          <p className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <CircleAlert className="size-4" aria-hidden="true" />
            Metrics unavailable: {metricsProblem}
          </p>
        )}
        <MetricTiles metrics={status.isPending ? undefined : metrics} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <ConnectionCard />
        {metrics ? (
          <OutcomesCard metrics={metrics} />
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Discovery outcomes</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {status.isPending ? 'Loading…' : 'Not available without a database connection.'}
            </CardContent>
          </Card>
        )}
      </div>

      <section>
        <h2 className="mb-3 text-sm font-medium text-foreground">Modules</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {modules.map(({ to, label, description, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className="group rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
            >
              <Card className="h-full transition-shadow group-hover:shadow-md">
                <CardContent className="flex items-start gap-4">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-foreground">{label}</p>
                    <p className="text-sm text-muted-foreground">{description}</p>
                  </div>
                  <ArrowRight
                    className="mt-1 size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
