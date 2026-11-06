import { ArrowRight, CircleAlert, CircleCheck, LoaderCircle, RefreshCw } from 'lucide-react'
import { Link } from 'react-router'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, XAxis, YAxis } from 'recharts'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useHealth } from '@/hooks/useHealth'
import { navItems } from '@/lib/navigation'
import { getErrorMessage } from '@/services/api'

// Nothing can be captured until ingestion exists, so every count is genuinely zero.
const sourceTypeCounts = ['Text', 'Audio', 'Video', 'Image', 'PDF'].map((source) => ({
  source,
  items: 0,
}))

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

function KnowledgeSourcesCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Captured knowledge by source</CardTitle>
        <CardDescription>
          No knowledge has been captured yet. Counts will appear once ingestion is available.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={sourceTypeCounts} margin={{ top: 8, right: 8, bottom: 0, left: -24 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="source"
                tickLine={false}
                axisLine={false}
                tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
              />
              <YAxis
                allowDecimals={false}
                domain={[0, 5]}
                ticks={[0, 1, 2, 3, 4, 5]}
                tickLine={false}
                axisLine={false}
                tick={{ fill: 'var(--muted-foreground)', fontSize: 12 }}
              />
              <Bar dataKey="items" fill="var(--chart-1)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const modules = navItems.filter((item) => item.to !== '/')

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-foreground">
          Welcome to Elisa Echo
        </h2>
        <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
          Preserve operational knowledge from network engineers and turn it into guided,
          evidence-backed troubleshooting.
        </p>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <ConnectionCard />
        <KnowledgeSourcesCard />
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
