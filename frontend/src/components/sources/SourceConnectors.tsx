import { Hash, Mail, MessageCircle, MessagesSquare, Upload, Users } from 'lucide-react'
import { type ChangeEvent, type ComponentType, useState } from 'react'

import { Disclosure } from '@/components/common/Disclosure'
import { Notice } from '@/components/common/States'
import { MailboxConnect } from '@/components/sources/MailboxConnect'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useEmailConnections, useEmailImport, useMailboxes } from '@/hooks/useSources'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { EmailImportResult, SlackStatus } from '@/types/api'

const DEMO_MAILBOX = 'ops-knowledge@elisa-echo.invalid'

type Key = 'slack' | 'teams' | 'email' | 'discord' | 'gchat'

interface Connector {
  key: Key
  name: string
  icon: ComponentType<{ className?: string }>
  tile: string
  preview?: { intake: string; scope: string }
}

const CONNECTORS: Connector[] = [
  { key: 'slack', name: 'Slack', icon: Hash, tile: 'bg-[#4A154B]' },
  {
    key: 'teams',
    name: 'Microsoft Teams',
    icon: Users,
    tile: 'bg-[#5059C9]',
    preview: {
      intake:
        'Microsoft Graph change notifications for channel and chat messages (Entra app registration, admin consent).',
      scope: 'Selected teams and channels only.',
    },
  },
  { key: 'email', name: 'Email', icon: Mail, tile: 'bg-[#EA4335]' },
  {
    key: 'discord',
    name: 'Discord',
    icon: MessagesSquare,
    tile: 'bg-[#5865F2]',
    preview: {
      intake: 'A Discord bot with the message-content intent, receiving gateway events.',
      scope: 'Selected servers and channels only.',
    },
  },
  {
    key: 'gchat',
    name: 'Google Chat',
    icon: MessageCircle,
    tile: 'bg-[#0F9D58]',
    preview: {
      intake: 'A Google Chat app subscribed to space events (Workspace Events API / Pub/Sub).',
      scope: 'Selected spaces only.',
    },
  },
]

const pill = 'rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap'

/** Where engineers already talk. Only Slack is a live connection; Email imports emails. */
export function SourceConnectors({
  slack,
  onManageSlack,
}: {
  slack: SlackStatus | undefined
  onManageSlack: () => void
}) {
  const connections = useEmailConnections()
  const [emailOpen, setEmailOpen] = useState(false)
  const [preview, setPreview] = useState<Connector | null>(null)
  const mailboxConnected = (connections.data ?? []).some(
    (c) => c.enabled && c.status === 'connected',
  )

  const status = (key: Key): { label: string; className: string; action: string } => {
    if (key === 'slack') {
      return slack?.connected
        ? {
            label: 'Connected',
            className: 'border-emerald-200 bg-emerald-50 text-emerald-800',
            action: 'Manage',
          }
        : {
            label: 'Not connected',
            className: 'border-amber-200 bg-amber-50 text-amber-900',
            action: 'Set up',
          }
    }
    if (key === 'email') {
      return mailboxConnected
        ? {
            label: 'Mailbox connected',
            className: 'border-emerald-200 bg-emerald-50 text-emerald-800',
            action: 'Manage',
          }
        : {
            label: 'Sample import',
            className: 'border-blue-200 bg-blue-50 text-blue-800',
            action: 'Connect',
          }
    }
    return { label: 'Preview', className: 'bg-muted text-muted-foreground', action: 'Connect' }
  }

  const open = (c: Connector) => {
    if (c.key === 'slack') onManageSlack()
    else if (c.key === 'email') setEmailOpen(true)
    else setPreview(c)
  }

  return (
    <section aria-labelledby="sources-title" className="flex flex-col gap-3">
      <h2 id="sources-title" className="text-base font-semibold text-foreground">
        Sources
      </h2>
      <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {CONNECTORS.map((c) => {
          const Icon = c.icon
          const s = status(c.key)
          return (
            <li
              key={c.key}
              className="flex items-center gap-3 rounded-xl border bg-card p-3 lg:flex-col lg:items-stretch"
            >
              <div className="flex min-w-0 flex-1 items-center gap-2.5">
                <span
                  className={cn(
                    'flex size-9 shrink-0 items-center justify-center rounded-lg text-white',
                    c.tile,
                  )}
                >
                  <Icon className="size-5" aria-hidden="true" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">
                    {c.name}
                  </span>
                  {s.label !== 'Preview' && s.label !== 'Sample import' && (
                    <span className={cn(pill, s.className)}>{s.label}</span>
                  )}
                </span>
              </div>
              <Button
                size="sm"
                variant={c.key === 'slack' ? 'outline' : 'secondary'}
                className={c.key === 'slack' ? undefined : 'bg-muted hover:bg-muted/70'}
                onClick={() => open(c)}
              >
                {s.action}
              </Button>
            </li>
          )
        })}
      </ul>

      <Dialog open={preview !== null} onOpenChange={(v) => !v && setPreview(null)}>
        <DialogContent>
          {preview && (
            <>
              <div className="flex items-center gap-3">
                <span
                  className={cn(
                    'flex size-10 items-center justify-center rounded-lg text-white',
                    preview.tile,
                  )}
                >
                  <preview.icon className="size-5" />
                </span>
                <div>
                  <DialogTitle>{preview.name}</DialogTitle>
                  <span className={cn(pill, 'bg-muted text-muted-foreground')}>
                    Preview, not connected
                  </span>
                </div>
              </div>
              <DialogDescription>
                This connector is not available yet. It would plug into the same pipeline Slack and
                email use today; nothing else changes.
              </DialogDescription>
              <ol className="flex flex-col gap-3 text-sm">
                {[
                  ['Capture', preview.preview?.intake ?? ''],
                  [
                    'Authorize',
                    `${preview.preview?.scope ?? ''} Each one is a source with an on/off allowlist, like Slack channels.`,
                  ],
                  [
                    'Discover and link',
                    'Threads are analyzed by the existing extraction, bound to nodes, sites and events, and consolidated with related cases.',
                  ],
                  [
                    'Use',
                    'Results appear in the Knowledge Explorer and guided troubleshooting with the original messages as evidence.',
                  ],
                ].map(([title, text], i) => (
                  <li key={title} className="flex gap-3">
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-foreground">
                      {i + 1}
                    </span>
                    <span>
                      <span className="block font-medium text-foreground">{title}</span>
                      <span className="text-muted-foreground">{text}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Sheet open={emailOpen} onOpenChange={setEmailOpen}>
        <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Mail className="size-4" aria-hidden="true" />
              Email
            </SheetTitle>
            <SheetDescription>
              Emails are threaded, cleaned of quoted history and analyzed like chat conversations.
            </SheetDescription>
          </SheetHeader>
          <div className="flex flex-col gap-4 px-4 pb-6 text-sm">
            <EmailImport />
            <Disclosure title="Connect a mailbox (IMAP, read-only)">
              <MailboxConnect />
            </Disclosure>
          </div>
        </SheetContent>
      </Sheet>
    </section>
  )
}

function EmailImport() {
  const mailboxes = useMailboxes()
  const { samples, upload } = useEmailImport()
  const [result, setResult] = useState<EmailImportResult | null>(null)
  const busy = samples.isPending || upload.isPending
  const error = samples.error ?? upload.error

  const onFiles = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length === 0) return
    const raws = await Promise.all(files.map((f) => f.text()))
    upload.mutate({ mailbox: DEMO_MAILBOX, raws }, { onSuccess: setResult })
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button disabled={busy} onClick={() => samples.mutate(undefined, { onSuccess: setResult })}>
          <Mail aria-hidden="true" />
          Import sample emails
        </Button>
        <Button variant="outline" disabled={busy} asChild>
          <label className="cursor-pointer">
            <Upload aria-hidden="true" />
            Upload .eml
            <input
              type="file"
              accept=".eml,message/rfc822"
              multiple
              className="sr-only"
              onChange={onFiles}
            />
          </label>
        </Button>
      </div>
      <p className="text-muted-foreground">
        The samples are the TRN-042 email thread from the Elisa brief and an older site-access
        email.
      </p>
      {result && (
        <Notice tone="info">
          {result.imported} imported, {result.duplicates} already known
          {result.threads.length > 0 &&
            `. Analyzing: ${result.threads.map((t) => t.title).join('; ')}`}
          {result.skipped_reason && `. ${result.skipped_reason}`}
        </Notice>
      )}
      {error != null && <Notice tone="error">{getErrorMessage(error)}</Notice>}
      {(mailboxes.data ?? []).length > 0 && (
        <ul className="flex flex-col divide-y rounded-lg border">
          {mailboxes.data?.map((m) => (
            <li key={m.id} className="flex items-center justify-between gap-2 px-3 py-2">
              <span className="truncate font-mono text-xs">{m.mailbox}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {m.threads} threads · {m.messages} emails
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
