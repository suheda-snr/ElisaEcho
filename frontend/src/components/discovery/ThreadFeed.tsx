import { CircleCheck, CircleDashed, LoaderCircle, TriangleAlert } from 'lucide-react'

import { SourceBadge } from '@/components/common/StatusBadges'
import { processingLabels } from '@/components/discovery/labels'
import { displayTitle } from '@/lib/displayTitle'
import { cn } from '@/lib/utils'
import type { Message, ThreadDiscovery } from '@/types/api'

interface ThreadListProps {
  threads: ThreadDiscovery[]
  selectedId: string | null
  activeId: string | null
  onSelect: (id: string) => void
}

/** Short forms for the fixed-width status slot in the conversation list. */
const shortProcessingLabels: Partial<Record<ThreadDiscovery['processing_status'], string>> = {
  pending: 'Queued',
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
    return { label: 'Failed', tone: 'text-red-700', icon: TriangleAlert }
  }
  const c = thread.candidate
  if (!c)
    return {
      label:
        shortProcessingLabels[thread.processing_status] ??
        processingLabels[thread.processing_status],
      tone: 'text-muted-foreground',
      icon: CircleDashed,
    }
  if (c.knowledge_item_id)
    return { label: 'Knowledge', tone: 'text-emerald-700', icon: CircleCheck }
  if (c.detection_status === 'rejected') {
    return { label: 'Not relevant', tone: 'text-muted-foreground', icon: CircleDashed }
  }
  return { label: 'No fix yet', tone: 'text-amber-700', icon: CircleDashed }
}

export function ThreadList({ threads, selectedId, activeId, onSelect }: ThreadListProps) {
  if (threads.length === 0) {
    return (
      <div className="flex items-start gap-3 rounded-lg border border-dashed px-3.5 py-6 text-[13px] leading-relaxed text-muted-foreground">
        <CircleDashed className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div className="min-w-0">
          No conversations yet. They appear here as soon as a connected channel receives messages.
        </div>
      </div>
    )
  }
  return (
    <ul className="flex flex-col gap-2" aria-label="Conversations">
      {threads.map((thread) => {
        const selected = thread.id === selectedId
        const outcome = outcomeOf(thread)
        const Icon = outcome.icon
        const title = displayTitle(thread.title ?? thread.external_thread_id)
        return (
          <li key={thread.id}>
            <button
              type="button"
              onClick={() => onSelect(thread.id)}
              aria-pressed={selected}
              title={title}
              className={cn(
                'flex w-full cursor-pointer flex-col gap-1.5 rounded-lg border px-3.5 py-3 text-left transition-colors duration-150',
                'focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none',
                selected
                  ? 'border-primary/30 bg-accent shadow-[inset_3px_0_0_var(--primary)]'
                  : 'bg-card hover:bg-muted/40',
              )}
            >
              <span className="flex items-start gap-2">
                <span className="line-clamp-2 min-w-0 flex-1 text-sm leading-snug font-medium [overflow-wrap:anywhere] text-foreground">
                  {title}
                </span>
                {thread.id === activeId && (
                  <span
                    className="mt-1.5 size-2 shrink-0 animate-pulse rounded-full bg-primary"
                    aria-label="New activity"
                  />
                )}
              </span>
              <span className="flex items-center gap-2 text-xs">
                <SourceBadge type={thread.source_type} className="shrink-0" />
                <span className="min-w-0 truncate text-muted-foreground tabular-nums">
                  {thread.message_count} {thread.message_count === 1 ? 'message' : 'messages'}
                </span>
                <span
                  className={cn(
                    'ml-auto inline-flex shrink-0 items-center gap-1 font-medium',
                    outcome.tone,
                  )}
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

/** A quiet, fixed palette so each author reads as the same person wherever they appear. */
const AVATAR_COLORS = [
  'bg-emerald-500',
  'bg-violet-500',
  'bg-sky-500',
  'bg-rose-500',
  'bg-amber-500',
  'bg-teal-500',
  'bg-indigo-500',
  'bg-fuchsia-500',
]

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
  // Assigned by order of first appearance in this conversation, so the handful of people
  // actually talking here get distinct colors rather than colliding on a global hash.
  const colorByAuthor = new Map<string, string>()
  const colorFor = (key: string) => {
    let color = colorByAuthor.get(key)
    if (!color) {
      color = AVATAR_COLORS[colorByAuthor.size % AVATAR_COLORS.length]
      colorByAuthor.set(key, color)
    }
    return color
  }
  // Every message is its own card, live or replayed alike — same component, same chrome,
  // whether the conversation streamed in moments ago or is being read back after the fact.
  return (
    <ol className="flex flex-col gap-3" aria-label="Messages">
      {messages.map((message, index) => {
        const isEvidence = highlighted.has(message.id)
        const author = message.author_display_name ?? message.author_external_id
        const color = colorFor(message.author_external_id || author)
        return (
          <li
            key={message.id}
            id={`message-${message.id}`}
            className="max-w-[48rem] animate-in duration-500 fade-in"
          >
            <div
              className={cn(
                'flex flex-col gap-2 rounded-xl border px-4 py-3',
                isEvidence ? 'border-primary/30 bg-insight/40' : 'bg-card',
              )}
            >
              <div className="flex items-center gap-2.5">
                <span
                  className={cn(
                    'flex size-7 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold text-white',
                    color,
                  )}
                  aria-hidden="true"
                >
                  {author.slice(0, 1).toUpperCase()}
                </span>
                <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
                  {author}
                </span>
                <time className="shrink-0 text-xs text-muted-foreground" dateTime={message.sent_at}>
                  {new Date(message.sent_at).toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </time>
                {isEvidence && (
                  <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-xs font-medium text-primary">
                    Evidence
                  </span>
                )}
                <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-xs text-muted-foreground">
                  #{index + 1}
                </span>
              </div>
              <p
                className={cn(
                  'pl-9 text-sm leading-relaxed whitespace-pre-wrap [overflow-wrap:anywhere] text-foreground',
                  message.deleted_at && 'text-muted-foreground line-through',
                )}
              >
                {message.content}
              </p>
            </div>
          </li>
        )
      })}
    </ol>
  )
}
