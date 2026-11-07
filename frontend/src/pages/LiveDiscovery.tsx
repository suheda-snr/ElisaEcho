import { BookOpenCheck, CircleAlert, Pause, Play, RotateCcw, Sparkles } from 'lucide-react'
import { type ReactNode, useEffect, useMemo, useState } from 'react'

import { KnowledgePanel } from '@/components/discovery/KnowledgePanel'
import { MessageList, ThreadList } from '@/components/discovery/ThreadFeed'
import { formatClock, resolutionLabels } from '@/components/discovery/labels'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  isPipelineBusy,
  useDiscoveryEvents,
  useDiscoveryStatus,
  useDiscoveryThreads,
  useKnowledgeItem,
  useKnowledgeItems,
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
  const knowledge = useKnowledgeItems(live)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [followLive, setFollowLive] = useState(true)
  const controls = useSimulationControls(() => {
    events.reset()
    setSelectedId(null)
    setFollowLive(true)
  })

  // The thread that most recently received a message.
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
  const itemId = selected?.candidate?.knowledge_item_id ?? null
  const item = useKnowledgeItem(itemId, live)

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
      <Card>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1">
              <h2 className="text-lg font-semibold text-foreground">Live knowledge discovery</h2>
              <p className="text-sm text-muted-foreground">
                Messages arrive from a simulated chat channel. Elisa Echo groups them into
                conversations and Gemini analyzes each conversation automatically. Nobody submits
                anything by hand.
              </p>
            </div>
            <Badge variant="outline">Synthetic demo data</Badge>
          </div>

          <div className="flex flex-wrap gap-2">
            {sim?.running ? (
              <Button
                variant="outline"
                onClick={() => controls.stop.mutate()}
                disabled={!devControls || controls.stop.isPending}
              >
                <Pause aria-hidden="true" />
                Stop simulation
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
              <a href="#discovered-knowledge">
                <BookOpenCheck aria-hidden="true" />
                View discovered knowledge
              </a>
            </Button>
            {!followLive && (
              <Button variant="ghost" onClick={() => setFollowLive(true)}>
                <Sparkles aria-hidden="true" />
                Follow live activity
              </Button>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Stat
              label="Simulation"
              value={
                sim
                  ? sim.running
                    ? `Running · ${sim.delivered + sim.skipped_duplicates}/${sim.total}`
                    : sim.finished_at
                      ? 'Finished'
                      : 'Stopped'
                  : '…'
              }
            />
            <Stat
              label="Delivered (new / duplicate)"
              value={sim ? `${sim.delivered} / ${sim.skipped_duplicates}` : '…'}
            />
            <Stat
              label="Analysis queue"
              value={analysis ? `${analysis.analyzing} running · ${analysis.queued} waiting` : '…'}
            />
            <Stat label="Model" value={analysis?.model ?? '…'} mono />
          </dl>

          {status.isError && <Alert>{getErrorMessage(status.error)}</Alert>}
          {analysis && !analysis.gemini_configured && (
            <Alert>
              Gemini is not configured (GEMINI_API_KEY is missing on the backend). Messages will
              still be ingested, but no knowledge can be discovered until a key is added.
            </Alert>
          )}
          {analysis?.paused_until && (
            <Alert>
              Gemini calls are paused until {formatClock(analysis.paused_until)} because the API
              quota is exhausted ({analysis.pause_reason}). Messages are still ingested; nothing is
              guessed in the meantime.
            </Alert>
          )}
          {status.data && !devControls && (
            <Alert>Simulation controls are only available in development.</Alert>
          )}
          {mutationError != null && <Alert>{getErrorMessage(mutationError)}</Alert>}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Communication feed</CardTitle>
            <CardDescription>Simulated Teams channel · Synthetic NOC chat (demo)</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
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
            {selected && (
              <div className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto border-t pt-4">
                <h3 className="sticky top-0 z-10 bg-card py-1 text-sm font-semibold text-foreground">
                  {selected.title ?? selected.external_thread_id}
                </h3>
                <MessageList
                  messages={messages.data?.items ?? []}
                  highlighted={highlighted}
                  isLoading={messages.isPending}
                />
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>AI knowledge discovery</CardTitle>
            <CardDescription>
              What Gemini extracted from the selected conversation, after server-side evidence
              checks
            </CardDescription>
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

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Pipeline activity</CardTitle>
            <CardDescription>Live events from the backend</CardDescription>
          </CardHeader>
          <CardContent>
            {events.events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No activity yet.</p>
            ) : (
              <ol className="flex max-h-80 flex-col-reverse gap-1.5 overflow-y-auto text-sm">
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

        <Card className="lg:col-span-3" id="discovered-knowledge">
          <CardHeader>
            <CardTitle>Discovered knowledge</CardTitle>
            <CardDescription>
              Stored in PostgreSQL · {knowledge.data?.total ?? 0} items · none approved
              automatically
            </CardDescription>
          </CardHeader>
          <CardContent>
            {knowledge.isError ? (
              <Alert>{getErrorMessage(knowledge.error)}</Alert>
            ) : (knowledge.data?.items.length ?? 0) === 0 ? (
              <p className="text-sm text-muted-foreground">No knowledge discovered yet.</p>
            ) : (
              <ul className="flex flex-col divide-y">
                {knowledge.data?.items.map((k) => (
                  <li key={k.id} className="flex flex-wrap items-center gap-2 py-2.5">
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
                    <Badge variant="secondary">{k.approval_status}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-lg border bg-muted/40 px-3 py-2">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={cn('truncate font-medium text-foreground', mono && 'font-mono text-xs')}>
        {value}
      </dd>
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
