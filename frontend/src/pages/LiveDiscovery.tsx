import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import { Disclosure } from '@/components/common/Disclosure'
import { Panel, PanelHeader } from '@/components/common/Panel'
import { Notice } from '@/components/common/States'
import { SourceBadge } from '@/components/common/StatusBadges'
import { KnowledgePanel } from '@/components/discovery/KnowledgePanel'
import { MessageList, ThreadList } from '@/components/discovery/ThreadFeed'
import { displayTitle } from '@/lib/displayTitle'
import { formatClock } from '@/components/discovery/labels'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
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

  // ?thread= opens a specific conversation (deep link); otherwise follow live activity.
  const [params] = useSearchParams()
  const [selectedId, setSelectedId] = useState<string | null>(params.get('thread'))
  const [followLive, setFollowLive] = useState(!params.get('thread'))
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

  const selectThread = (id: string) => {
    setSelectedId(id)
    setFollowLive(false)
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader>
        <div className="flex flex-wrap items-center gap-3" aria-live="polite">
          {sim?.running && (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <span className="size-1.5 animate-pulse rounded-full bg-primary" aria-hidden="true" />
              Demo feed {sim.delivered + sim.skipped_duplicates}/{sim.total}
            </span>
          )}
          {!followLive && (
            <Button variant="ghost" size="sm" className="h-7" onClick={() => setFollowLive(true)}>
              Follow live activity
            </Button>
          )}
        </div>
      </PageHeader>

      {status.isError && <Notice tone="error">{getErrorMessage(status.error)}</Notice>}

      {/* Three panels, same card language as the rest of the app: a bordered white surface
          with its own header, instead of one box pretending to be three widgets. */}
      <div className="grid gap-4 md:grid-cols-[minmax(15rem,0.8fr)_minmax(0,1.4fr)] md:grid-rows-[34rem_auto] xl:h-[calc(100dvh-13.5rem)] xl:min-h-[34rem] xl:grid-cols-[minmax(17rem,0.9fr)_minmax(0,1.45fr)_minmax(19rem,1fr)] xl:grid-rows-1 2xl:grid-cols-[minmax(19rem,0.85fr)_minmax(0,1.5fr)_minmax(21rem,0.95fr)]">
        <Panel className="flex min-h-0 flex-col" aria-label="Conversations">
          <PanelHeader title="Conversations" meta={threadItems.length || undefined} />
          <div className="max-h-[26rem] min-h-0 flex-1 overflow-y-auto p-3 md:max-h-none">
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
          </div>
        </Panel>

        <Panel className="flex min-h-0 flex-col" aria-label="Messages">
          <PanelHeader
            title={
              selected ? (
                <span className="block truncate" title={displayTitle(selected.title ?? '')}>
                  {displayTitle(selected.title ?? selected.external_thread_id)}
                </span>
              ) : (
                'Messages'
              )
            }
            meta={
              selected && (
                <span className="flex items-center gap-2">
                  <SourceBadge type={selected.source_type} />
                </span>
              )
            }
          />
          <div className="max-h-[30rem] min-h-0 flex-1 overflow-y-auto bg-canvas/40 px-4 py-4 md:max-h-none">
            {selected ? (
              <MessageList
                messages={messages.data?.items ?? []}
                highlighted={highlighted}
                isLoading={messages.isPending}
              />
            ) : (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Select a conversation.
              </p>
            )}
          </div>
        </Panel>

        <Panel
          className="flex min-h-0 flex-col md:col-span-2 xl:col-span-1"
          aria-label="Discovered context"
        >
          <PanelHeader title="Discovered context" />
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
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
          </div>
        </Panel>
      </div>

      <Disclosure
        title={<span className="text-muted-foreground">Activity log</span>}
        count={events.events.length}
        className="-mt-3 border-transparent bg-transparent [&>summary]:px-2 [&>summary]:text-[13px]"
      >
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
