import { FlaskConical, Hash, LoaderCircle, Pause, Play, RotateCcw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Disclosure } from '@/components/common/Disclosure'
import { Notice } from '@/components/common/States'
import { SourceBadge } from '@/components/common/StatusBadges'
import { KnowledgePanel } from '@/components/discovery/KnowledgePanel'
import { MessageList, ThreadList } from '@/components/discovery/ThreadFeed'
import { formatClock } from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  isPipelineBusy,
  useDiscoveryEvents,
  useDiscoveryStatus,
  useDiscoveryThreads,
  useKnowledgeItem,
  useSimulationControls,
  useThreadMessages,
} from '@/hooks/useDiscovery'
import { useSlackStatus } from '@/hooks/useIntegrations'
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
  const slack = useSlackStatus()
  const live = isPipelineBusy(status.data)
  const threads = useDiscoveryThreads(live)
  const events = useDiscoveryEvents(live)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [followLive, setFollowLive] = useState(true)
  const [demoOpen, setDemoOpen] = useState(false)
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

  // Keep the newest message in view while following live activity.
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
  const busy = (analysis?.analyzing ?? 0) + (analysis?.queued ?? 0)

  const selectThread = (id: string) => {
    setSelectedId(id)
    setFollowLive(false)
  }

  const onReset = () => {
    if (
      window.confirm(
        'Delete the synthetic demo conversations and the knowledge discovered from them? Slack and other data are not affected.',
      )
    ) {
      controls.reset.mutate()
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        actions={
          <Button
            variant={demoOpen || sim?.running ? 'secondary' : 'outline'}
            onClick={() => setDemoOpen((v) => !v)}
            aria-expanded={demoOpen}
          >
            <FlaskConical aria-hidden="true" />
            Demo mode
            {sim?.running && <span className="size-2 animate-pulse rounded-full bg-primary" />}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
          <span className="inline-flex items-center gap-1.5">
            <Hash
              className={cn(
                'size-4',
                slack.data?.connected ? 'text-emerald-600' : 'text-muted-foreground',
              )}
              aria-hidden="true"
            />
            {slack.data?.connected
              ? `Slack connected · ${slack.data.monitored_channels.length} channel(s)`
              : 'Slack not connected'}
          </span>
          <span className="inline-flex items-center gap-1.5 text-muted-foreground">
            {busy > 0 && (
              <LoaderCircle className="size-4 animate-spin text-primary" aria-hidden="true" />
            )}
            {!analysis
              ? 'AI status…'
              : !analysis.gemini_configured
                ? 'AI analysis not configured'
                : analysis.paused_until
                  ? `AI paused until ${formatClock(analysis.paused_until)} (quota)`
                  : busy > 0
                    ? `Analyzing ${busy} conversation(s)`
                    : 'AI idle'}
          </span>
          {sim?.running && (
            <span className="text-muted-foreground">
              Demo feed {sim.delivered + sim.skipped_duplicates}/{sim.total}
            </span>
          )}
          {!followLive && (
            <Button variant="ghost" size="sm" onClick={() => setFollowLive(true)}>
              Follow live activity
            </Button>
          )}
        </div>
      </PageHeader>

      {demoOpen && (
        <Card>
          <CardContent className="flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium text-foreground">Demo mode</span>
              <span className="text-sm text-muted-foreground">
                Streams synthetic chat, Teams and email conversations (incl. the TRN-042 case)
                through the same pipeline as Slack.
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {sim?.running ? (
                <Button
                  variant="outline"
                  onClick={() => controls.stop.mutate()}
                  disabled={!devControls || controls.stop.isPending}
                >
                  <Pause aria-hidden="true" />
                  Stop feed
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
                  Start demo feed
                </Button>
              )}
              <Button
                variant="ghost"
                onClick={onReset}
                disabled={!devControls || controls.reset.isPending}
              >
                <RotateCcw aria-hidden="true" />
                Reset demo data
              </Button>
              {sim && sim.total > 0 && (
                <span className="flex min-w-40 flex-1 items-center gap-2 text-xs text-muted-foreground tabular-nums">
                  <span
                    className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted"
                    aria-hidden="true"
                  >
                    <span
                      className="block h-full rounded-full bg-primary transition-all"
                      style={{ width: `${Math.round(progress * 100)}%` }}
                    />
                  </span>
                  {sim.delivered + sim.skipped_duplicates}/{sim.total}
                </span>
              )}
            </div>
            {!devControls && status.data && (
              <p className="text-sm text-muted-foreground">
                Demo controls are available in development only.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {status.isError && <Notice tone="error">{getErrorMessage(status.error)}</Notice>}
      {mutationError != null && <Notice tone="error">{getErrorMessage(mutationError)}</Notice>}

      <div className="grid gap-5 lg:grid-cols-12">
        <Card className="gap-3 lg:col-span-4">
          <CardHeader>
            <CardTitle>Conversations</CardTitle>
          </CardHeader>
          <CardContent className="max-h-[40rem] overflow-y-auto">
            {threads.isError ? (
              <Notice tone="error">{getErrorMessage(threads.error)}</Notice>
            ) : (
              <ThreadList
                threads={threadItems}
                selectedId={selected?.id ?? null}
                activeId={sim?.running ? activeId : null}
                onSelect={selectThread}
              />
            )}
          </CardContent>
        </Card>

        <Card className="gap-3 lg:col-span-4">
          <CardHeader>
            <CardTitle className="truncate" title={selected?.title ?? undefined}>
              {selected?.title ?? 'Messages'}
            </CardTitle>
            {selected && (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <SourceBadge type={selected.source_type} />
                {selected.source_name && <span className="truncate">{selected.source_name}</span>}
              </p>
            )}
          </CardHeader>
          <CardContent>
            <div className="max-h-[40rem] overflow-y-auto pr-1">
              {selected ? (
                <MessageList
                  messages={messages.data?.items ?? []}
                  highlighted={highlighted}
                  isLoading={messages.isPending}
                />
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  Select a conversation.
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="gap-3 lg:col-span-4">
          <CardHeader>
            <CardTitle>Discovered context</CardTitle>
          </CardHeader>
          <CardContent>
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
          </CardContent>
        </Card>
      </div>

      <Disclosure title="Activity log" count={events.events.length}>
        {events.events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No activity yet.</p>
        ) : (
          <ol className="flex max-h-80 flex-col-reverse gap-1.5 overflow-y-auto text-sm">
            {events.events.map((e) => (
              <li key={e.id} className="flex gap-3">
                <span className="shrink-0 font-mono text-xs leading-5 text-muted-foreground tabular-nums">
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
      </Disclosure>
    </div>
  )
}
