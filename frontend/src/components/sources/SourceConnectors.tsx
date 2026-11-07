import { CircleCheck, Hash, Mail, MessageCircle, MessagesSquare, Users } from 'lucide-react'
import { type ComponentType, useState } from 'react'

import { MailboxConnect } from '@/components/sources/MailboxConnect'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useEmailConnections } from '@/hooks/useSources'
import { cn } from '@/lib/utils'
import type { SlackStatus } from '@/types/api'

interface Connector {
  key: string
  name: string
  hint: string
  icon: ComponentType<{ className?: string }>
  tile: string
}

const CONNECTORS: Connector[] = [
  { key: 'slack', name: 'Slack', hint: 'Channels', icon: Hash, tile: 'bg-[#4A154B] text-white' },
  {
    key: 'teams',
    name: 'Microsoft Teams',
    hint: 'Chats and channels',
    icon: Users,
    tile: 'bg-[#5059C9] text-white',
  },
  {
    key: 'email',
    name: 'Email',
    hint: 'Gmail, Outlook (IMAP)',
    icon: Mail,
    tile: 'bg-[#EA4335] text-white',
  },
  {
    key: 'discord',
    name: 'Discord',
    hint: 'Servers and channels',
    icon: MessagesSquare,
    tile: 'bg-[#5865F2] text-white',
  },
  {
    key: 'gchat',
    name: 'Google Chat',
    hint: 'Spaces',
    icon: MessageCircle,
    tile: 'bg-[#0F9D58] text-white',
  },
]

/** One row of sources: connect where engineers already talk. */
export function SourceConnectors({ slack }: { slack: SlackStatus | undefined }) {
  const email = useEmailConnections()
  const [emailOpen, setEmailOpen] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const emailConnected = (email.data ?? []).filter((c) => c.enabled)

  const connected: Record<string, string | null> = {
    slack: slack?.connected ? (slack.workspace_name ?? 'Workspace connected') : null,
    email: emailConnected.length ? emailConnected.map((c) => c.username).join(', ') : null,
  }

  const onConnect = (key: string) => {
    setNotice(null)
    if (key === 'email') setEmailOpen(true)
    else if (key === 'slack')
      document.getElementById('slack-connection')?.scrollIntoView({ behavior: 'smooth' })
    else setNotice(key)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Connect your sources</CardTitle>
        <CardDescription>
          Knowledge is captured where engineers already talk. Connect a source once; nothing else
          changes for the experts.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {CONNECTORS.map((c) => {
            const Icon = c.icon
            const status = connected[c.key]
            return (
              <li key={c.key} className="flex flex-col gap-3 rounded-xl border bg-card p-3">
                <div className="flex items-center gap-2.5">
                  <span
                    className={cn(
                      'flex size-9 shrink-0 items-center justify-center rounded-lg',
                      c.tile,
                    )}
                  >
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-foreground">{c.name}</span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {status ?? c.hint}
                    </span>
                  </span>
                </div>
                {status ? (
                  <Button size="sm" variant="outline" onClick={() => onConnect(c.key)}>
                    <CircleCheck className="text-emerald-700" aria-hidden="true" />
                    Connected
                  </Button>
                ) : (
                  <Button size="sm" onClick={() => onConnect(c.key)}>
                    Connect
                  </Button>
                )}
                {notice === c.key && (
                  <p className="text-xs text-muted-foreground">
                    Coming soon. The discovery pipeline is source-independent; this connector is not
                    available in the demo yet.
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      </CardContent>

      <Sheet open={emailOpen} onOpenChange={setEmailOpen}>
        <SheetContent side="right" className="w-full gap-0 overflow-y-auto sm:max-w-md">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Mail className="size-4" aria-hidden="true" />
              Email
            </SheetTitle>
            <SheetDescription>
              Connect a mailbox folder or label. New emails are read every minute (read-only) and
              analyzed like chat conversations.
            </SheetDescription>
          </SheetHeader>
          <div className="px-4 pb-6 text-sm">
            <MailboxConnect />
          </div>
        </SheetContent>
      </Sheet>
    </Card>
  )
}
