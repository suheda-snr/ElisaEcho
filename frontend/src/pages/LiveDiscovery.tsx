import { BookOpenText, CircleAlert, Pause, Play, RotateCcw } from 'lucide-react'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { KnowledgePanel } from '@/components/discovery/KnowledgePanel'
import { MessageList, ThreadList } from '@/components/discovery/ThreadFeed'
import { formatClock } from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Tabs } from '@/components/Tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  isPipelineBusy,
  useDiscoveryEvents,
  useDiscoveryStatus,
  useDiscoveryThreads,
  useKnowledgeItem,
  useSimulationControls,
  useThreadMessages,
} from '@/hooks/useDiscovery'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'

const levelStyles = {
  info: 'text-muted-foreground',
  success: 'text-emerald-700',
  warning: 'text-amber-700',
  error: 'text-red-700',
} as const

export default function LiveDiscovery() {
  const status = useDiscoveryStatus()
  const live = isPipelineBusy(status.data)
  const threads = useDiscoveryThreads(live)
  const events = useDiscoveryEvents(live)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [followLive, setFollowLive] = useState(true)
  const [tab, setTab] = useState<'analysis' | 'activity'>('analysis')
  const controls = useSimulationControls(() => {
    events.reset()
    setSelectedId(null)
    setFollowLive(true)
  })

  // The conversation that most recently received a message.
  const activeId = useMemo(() => {
    for (let i = events.events.length - 1; i >= 0; i--) {
      const e = events.events[i]
      if (e.kind === 'message_received' && e.thread_id) return e.thread_id
    }
    return null
  }, [events.events])

  const threadItems = useMemo(() => threads.data?.items ?? [], [threads.data])
  const effectiveId =
    (followLive && activeId) || selectedId || (threadItems.length > 0 ? threadItems[0].id : null)
  const selected = threadItems.find((t) => t.id === effectiveId) ?? null

  const messages = useThreadMessages(selected?.id ?? null, live)
  const item = useKnowledgeItem(selected?.candidate?.knowledge_item_id ?? null, live)
  const highlighted = useMemo(
    () => new Set(item.data?.evidence.map((e) => e.message.id) ?? []),
    [item.data],
  )

  // Keep the newest message in view while following the live feed.
  const messageCount = messages.data?.items.length ?? 0
  useEffect(() => {
    if (!followLive || messageCount === 0) return
    const last = messages.data?.items[messageCount - 1]
    if (last) document.getElementById(`message-${last.id}`)?.scrollIntoView({ block: 'nearest' })
  }, [followLive, messageCount, messages.data])

  const sim = status.data?.simulation
  const analysis = status.data?.analysis
  const devControls = status.data?.development_controls ?? false
  const mutationError = controls.start.error ?? controls.stop.error ?? controls.reset.error
  const progress = sim && sim.total > 0 ? (sim.delivered + sim.skipped_duplicates) / sim.total : 0

  const selectThread = (id: string) => {
    setSelectedId(id)
    setFollowLive(false)
  }

  const onReset = () => {
    if (
      window.confirm(
        'Delete all synthetic demo conversations and the knowledge discovered from them? Other data is not affected.',
      )
    ) {
      controls.reset.mutate()
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        actions={
          <>
            {sim?.running ? (
              <Button
                variant="outline"
                onClick={() => controls.stop.mutate()}
                disabled={!devControls || controls.stop.isPending}
              >
                <Pause aria-hidden="true" />
                Stop
              </Button>
            ) : (
              <Button
                onClick={() => {
                  setFollowLive(true)
                  controls.start.mutate()
                }}
                disabled={!devControls || controls.start.isPending || !status.data}
              >
                <Play aria-hidden="true" />
                Start simulation
              </Button>
            )}
            <Button
              variant="outline"
              onClick={onReset}
              disabled={!devControls || controls.reset.isPending}
            >
              <RotateCcw aria-hidden="true" />
              Reset demo
            </Button>
            <Button variant="ghost" asChild>
              <Link to="/knowledge">
                <BookOpenText aria-hidden="true" />
                Knowledge Base
              </Link>
            </Button>
          </>
        }
      >
        {/* Status strip */}
        <div className="flex flex-col gap-3 rounded-xl border bg-card px-4 py-3 sm:flex-row sm:items-center sm:gap-6">
          <div className="flex min-w-0 flex-1 flex-col gap-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium text-foreground">
                {sim?.running
                  ? 'Simulated chat feed running'
                  : sim?.finished_at
                    ? 'Feed finished'
                    : sim && sim.total === 0
                      ? 'Ready: press Start simulation to stream synthetic chat messages'
                      : 'Feed stopped'}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {sim ? `${sim.delivered + sim.skipped_duplicates} / ${sim.total} messages` : '…'}
                {sim &&
                  sim.skipped_duplicates > 0 &&
                  ` · ${sim.skipped_duplicates} duplicates ignored`}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="secondary">
              AI: {analysis ? `${analysis.analyzing} analyzing · ${analysis.queued} waiting` : '…'}
            </Badge>
            <Badge variant="outline" className="font-mono">
              {analysis?.model ?? '…'}
            </Badge>
            <Badge variant="outline">Synthetic data</Badge>
          </div>
        </div>
      </PageHeader>

      {(status.isError ||
        (analysis && !analysis.gemini_configured) ||
        analysis?.paused_until ||
        (status.data && !devControls) ||
        mutationError != null) && (
        <div className="flex flex-col gap-2">
          {status.isError && <Alert>{getErrorMessage(status.error)}</Alert>}
          {analysis && !analysis.gemini_configured && (
            <Alert>
              Gemini is not configured (GEMINI_API_KEY is missing on the backend). Messages are
              still received, but no knowledge can be discovered.
            </Alert>
          )}
          {analysis?.paused_until && (
            <Alert>
              AI analysis is paused until {formatClock(analysis.paused_until)} because the Gemini
              quota is exhausted. Messages are still received; nothing is guessed meanwhile.
            </Alert>
          )}
          {status.data && !devControls && (
            <Alert>Simulation controls are only available in development.</Alert>
          )}
          {mutationError != null && <Alert>{getErrorMessage(mutationError)}</Alert>}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        {/* 1. Conversations */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Conversations</CardTitle>
            <CardDescription>Monitored Slack channels and the simulated feed</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {threads.isError ? (
              <Alert>{getErrorMessage(threads.error)}</Alert>
            ) : (
              <ThreadList
                threads={threadItems}
                selectedId={selected?.id ?? null}
                activeId={sim?.running ? activeId : null}
                onSelect={selectThread}
              />
            )}
            {!followLive && sim?.running && (
              <Button variant="ghost" size="sm" onClick={() => setFollowLive(true)}>
                Follow live activity
              </Button>
            )}
          </CardContent>
        </Card>

        {/* 2. Messages */}
        <Card className="lg:col-span-4">
          <CardHeader>
            <CardTitle className="truncate">{selected?.title ?? 'Messages'}</CardTitle>
            <CardDescription>
              {selected
                ? `${selected.message_count} messages · highlighted ones are cited as evidence`
                : 'Select a conversation'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="max-h-[36rem] overflow-y-auto pr-1">
              {selected ? (
                <MessageList
                  messages={messages.data?.items ?? []}
                  highlighted={highlighted}
                  isLoading={messages.isPending}
                />
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No conversations yet. Press Start simulation.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* 3. AI result + activity */}
        <Card className="lg:col-span-5">
          <CardHeader className="gap-3">
            <Tabs
              label="Discovery details"
              value={tab}
              onChange={setTab}
              tabs={[
                { value: 'analysis', label: 'AI analysis' },
                { value: 'activity', label: 'Activity log', count: events.events.length },
              ]}
            />
          </CardHeader>
          <CardContent>
            {tab === 'analysis' ? (
              <KnowledgePanel
                thread={selected}
                item={item.data}
                itemLoading={item.isPending}
                itemError={item.error}
                messages={messages.data?.items ?? []}
                geminiConfigured={analysis?.gemini_configured ?? false}
                onRetry={
                  devControls && selected ? () => controls.analyze.mutate(selected.id) : undefined
                }
                retrying={controls.analyze.isPending}
                retryError={controls.analyze.error}
              />
            ) : events.events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No activity yet.</p>
            ) : (
              <ol className="flex max-h-[36rem] flex-col-reverse gap-1.5 overflow-y-auto text-sm">
                {events.events.map((e) => (
                  <li key={e.id} className="flex gap-2">
                    <span className="shrink-0 font-mono text-xs text-muted-foreground tabular-nums">
                      {formatClock(e.at)}
                    </span>
                    <span className={cn('min-w-0', levelStyles[e.level])}>
                      {e.thread_title && (
                        <span className="font-medium text-foreground">{e.thread_title}: </span>
                      )}
                      {e.message}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Alert({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}
