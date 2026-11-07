import { CircleCheck, CircleDashed, LoaderCircle, TriangleAlert } from 'lucide-react'

import { SourceBadge } from '@/components/common/StatusBadges'
import { processingLabels } from '@/components/discovery/labels'
import { cn } from '@/lib/utils'
import type { Message, ThreadDiscovery } from '@/types/api'

interface ThreadListProps {
  threads: ThreadDiscovery[]
  selectedId: string | null
  activeId: string | null
  onSelect: (id: string) => void
}

/** What happened to the conversation, as one short status. */
function outcomeOf(thread: ThreadDiscovery): {
  label: string
  tone: string
  icon: typeof CircleCheck
} {
  if (thread.processing_status === 'processing') {
    return { label: 'Analyzing…', tone: 'text-primary', icon: LoaderCircle }
  }
  if (thread.processing_status === 'failed') {
    return { label: 'Analysis failed', tone: 'text-red-700', icon: TriangleAlert }
  }
  const c = thread.candidate
  if (!c)
    return {
      label: processingLabels[thread.processing_status],
      tone: 'text-muted-foreground',
      icon: CircleDashed,
    }
  if (c.knowledge_item_id)
    return { label: 'Knowledge found', tone: 'text-emerald-700', icon: CircleCheck }
  if (c.detection_status === 'rejected') {
    return { label: 'Not relevant', tone: 'text-muted-foreground', icon: CircleDashed }
  }
  return { label: 'Issue, no fix yet', tone: 'text-amber-700', icon: CircleDashed }
}

export function ThreadList({ threads, selectedId, activeId, onSelect }: ThreadListProps) {
  if (threads.length === 0) {
    return (
      <p className="rounded-lg border border-dashed px-3 py-8 text-center text-sm text-muted-foreground">
        No conversations yet. They appear here as soon as a connected channel receives messages.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-1" aria-label="Conversations">
      {threads.map((thread) => {
        const selected = thread.id === selectedId
        const outcome = outcomeOf(thread)
        const Icon = outcome.icon
        const title = thread.title ?? thread.external_thread_id
        return (
          <li key={thread.id}>
            <button
              type="button"
              onClick={() => onSelect(thread.id)}
              aria-pressed={selected}
              title={title}
              className={cn(
                'flex w-full flex-col gap-1 rounded-lg border px-3 py-2.5 text-left transition-colors',
                'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                selected ? 'border-primary/40 bg-accent' : 'border-transparent hover:bg-muted/60',
              )}
            >
              <span className="flex items-center gap-2">
                {thread.id === activeId && (
                  <span
                    className="size-2 shrink-0 animate-pulse rounded-full bg-primary"
                    aria-label="New activity"
                  />
                )}
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                  {title}
                </span>
              </span>
              <span className="flex items-center gap-3 text-xs">
                <SourceBadge type={thread.source_type} />
                <span className="text-muted-foreground tabular-nums">
                  {thread.message_count} msg
                </span>
                <span
                  className={cn('ml-auto inline-flex items-center gap-1 font-medium', outcome.tone)}
                >
                  <Icon
                    className={cn(
                      'size-3.5',
                      thread.processing_status === 'processing' && 'animate-spin',
                    )}
                    aria-hidden="true"
                  />
                  {outcome.label}
                </span>
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

interface MessageListProps {
  messages: Message[]
  highlighted: Set<string>
  isLoading: boolean
}

export function MessageList({ messages, highlighted, isLoading }: MessageListProps) {
  if (isLoading) {
    return <p className="py-6 text-center text-sm text-muted-foreground">Loading messages…</p>
  }
  if (messages.length === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">No messages yet.</p>
  }
  return (
    <ol className="flex flex-col gap-3" aria-label="Messages">
      {messages.map((message, index) => {
        const isEvidence = highlighted.has(message.id)
        return (
          <li
            key={message.id}
            id={`message-${message.id}`}
            className="animate-in duration-500 fade-in"
          >
            <div className="mb-1 flex items-baseline gap-2 text-xs">
              <span className="font-semibold text-foreground">
                {message.author_display_name ?? message.author_external_id}
              </span>
              <span className="text-muted-foreground">
                {new Date(message.sent_at).toLocaleString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
              <span className="ml-auto flex items-center gap-1.5 font-mono text-muted-foreground">
                {isEvidence && (
                  <span className="rounded bg-primary/10 px-1.5 font-sans font-medium text-primary">
                    Evidence
                  </span>
                )}
                #{index + 1}
              </span>
            </div>
            <p
              className={cn(
                'rounded-lg px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap text-foreground',
                isEvidence ? 'border-l-3 border-primary bg-accent' : 'bg-muted/50',
                message.deleted_at && 'text-muted-foreground line-through',
              )}
            >
              {message.content}
            </p>
          </li>
        )
      })}
    </ol>
  )
}
