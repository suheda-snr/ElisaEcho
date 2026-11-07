import { MessageSquare, Radio } from 'lucide-react'

import { processingLabels } from '@/components/discovery/labels'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Message, ThreadDiscovery } from '@/types/api'

interface ThreadListProps {
  threads: ThreadDiscovery[]
  selectedId: string | null
  activeId: string | null
  onSelect: (id: string) => void
}

export function ThreadList({ threads, selectedId, activeId, onSelect }: ThreadListProps) {
  if (threads.length === 0) {
    return (
      <p className="rounded-lg border border-dashed px-3 py-6 text-center text-sm text-muted-foreground">
        No conversations yet. Start the simulation to receive messages.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-1.5" aria-label="Conversation threads">
      {threads.map((thread) => {
        const selected = thread.id === selectedId
        const busy = thread.processing_status === 'processing'
        return (
          <li key={thread.id}>
            <button
              type="button"
              onClick={() => onSelect(thread.id)}
              aria-pressed={selected}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors',
                'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                selected ? 'border-primary/40 bg-accent' : 'bg-background hover:bg-muted/60',
              )}
            >
              <span className="relative flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                <MessageSquare className="size-4" aria-hidden="true" />
                {thread.id === activeId && (
                  <span
                    className="absolute -top-0.5 -right-0.5 size-2.5 animate-pulse rounded-full bg-primary"
                    aria-label="New activity"
                  />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground">
                  {thread.title ?? thread.external_thread_id}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {thread.message_count} messages · {processingLabels[thread.processing_status]}
                </span>
              </span>
              {busy && <Radio className="size-4 animate-pulse text-primary" aria-hidden="true" />}
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
            className="animate-in duration-500 fade-in slide-in-from-bottom-2"
          >
            <div className="mb-1 flex items-baseline gap-2 text-xs">
              <span className="font-medium text-foreground">
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
              <span className="ml-auto font-mono text-muted-foreground">#{index + 1}</span>
            </div>
            <p
              className={cn(
                'rounded-lg border px-3 py-2 text-sm whitespace-pre-wrap text-foreground',
                isEvidence ? 'border-primary/50 bg-accent' : 'bg-background',
                message.deleted_at && 'text-muted-foreground line-through',
              )}
            >
              {message.content}
            </p>
            {isEvidence && (
              <Badge variant="outline" className="mt-1">
                Cited as evidence
              </Badge>
            )}
          </li>
        )
      })}
    </ol>
  )
}
