import { CircleCheck, CircleDashed, Hash, LoaderCircle, Plus, ShieldCheck } from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { Link } from 'react-router'

import { Disclosure } from '@/components/common/Disclosure'
import { Loading, Notice } from '@/components/common/States'
import { formatTime } from '@/components/discovery/labels'
import { SourceConnectors } from '@/components/sources/SourceConnectors'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useDiscoveryStatus } from '@/hooks/useDiscovery'
import {
  useSetSlackChannel,
  useSlackChannels,
  useSlackEvents,
  useSlackStatus,
} from '@/hooks/useIntegrations'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { SlackChannel, SlackStatus, SlackStatusValue } from '@/types/api'

const statusInfo: Record<
  SlackStatusValue,
  { label: string; tone: 'ok' | 'warn' | 'error' | 'off'; text: string }
> = {
  connected: {
    label: 'Connected',
    tone: 'ok',
    text: 'Credentials verified and the Socket Mode connection is open. New messages in monitored channels are analyzed automatically.',
  },
  connecting: {
    label: 'Connecting',
    tone: 'warn',
    text: 'The worker verified the credentials and is opening the connection.',
  },
  disconnected: {
    label: 'Disconnected',
    tone: 'warn',
    text: 'The connection to Slack dropped. The worker reconnects automatically.',
  },
  worker_not_running: {
    label: 'Worker not running',
    tone: 'warn',
    text: 'Slack is configured, but the slack-worker service is not reporting. Start it with Docker Compose.',
  },
  error: {
    label: 'Error',
    tone: 'error',
    text: 'Slack rejected the credentials or could not be reached.',
  },
  not_configured: {
    label: 'Not configured',
    tone: 'off',
    text: 'Slack is enabled but the tokens are missing. An administrator must create the Slack app first.',
  },
  disabled: {
    label: 'Not set up',
    tone: 'off',
    text: 'The Slack integration is turned off. An administrator installs the Slack app and configures the backend; there is no in-app sign-in.',
  },
}

const toneClass = {
  ok: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  warn: 'border-amber-200 bg-amber-50 text-amber-900',
  error: 'border-red-200 bg-red-50 text-red-800',
  off: 'border-slate-200 bg-slate-50 text-slate-700',
}

export default function Integrations() {
  const status = useSlackStatus()
  const discovery = useDiscoveryStatus()
  const data = status.data
  const manageSlack = () =>
    document.getElementById('slack')?.scrollIntoView({ behavior: 'smooth', block: 'start' })

  return (
    <div className="flex flex-col gap-6">
      <PageHeader description="Elisa Echo only reads sources an administrator has authorized." />

      {status.isError && <Notice tone="error">{getErrorMessage(status.error)}</Notice>}

      <SourceConnectors slack={data} onManageSlack={manageSlack} />

      <div id="slack" className="scroll-mt-24">
        {data ? <SlackCard status={data} /> : <Loading />}
      </div>

      <p className="text-sm text-muted-foreground">
        No workspace at hand? The demo feed in{' '}
        <Link to="/discovery" className="font-medium text-primary hover:underline">
          Live Discovery
        </Link>{' '}
        streams synthetic conversations through the same pipeline
        {discovery.data?.simulation.running ? ' (running now)' : ''}.
      </p>
    </div>
  )
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-3">
      <dt className="w-40 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-foreground">{children}</dd>
    </div>
  )
}

function Check({ ok, children }: { ok: boolean; children: ReactNode }) {
  const Icon = ok ? CircleCheck : CircleDashed
  return (
    <li className="flex items-center gap-2">
      <Icon
        className={cn('size-4', ok ? 'text-emerald-600' : 'text-muted-foreground')}
        aria-hidden="true"
      />
      <span className={ok ? 'text-foreground' : 'text-muted-foreground'}>{children}</span>
    </li>
  )
}

function SlackCard({ status }: { status: SlackStatus }) {
  const info = statusInfo[status.status]
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-lg bg-[#4A154B] text-white">
            <Hash className="size-5" aria-hidden="true" />
          </span>
          <div>
            <CardTitle>Slack</CardTitle>
            <p className="text-sm text-muted-foreground">
              {status.workspace_name ?? 'No workspace connected'}
            </p>
          </div>
        </div>
        <span
          className={cn('rounded-full border px-3 py-1 text-sm font-medium', toneClass[info.tone])}
        >
          {info.label}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm">
        <p className="text-foreground/80">{info.text}</p>
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Monitored channels</dt>
            <dd className="mt-1 flex flex-wrap gap-1.5">
              {status.monitored_channels.length === 0 ? (
                <span className="text-foreground">None yet</span>
              ) : (
                status.monitored_channels.map((c) => (
                  <Badge key={c.channel_id} variant="secondary">
                    #{c.name.replace(/^#/, '')}
                  </Badge>
                ))
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Last message stored</dt>
            <dd className="mt-1 text-foreground">
              {status.last_ingested_at ? formatTime(status.last_ingested_at) : '–'}
            </dd>
          </div>
        </dl>
        {status.last_error && <Notice tone="error">{status.last_error}</Notice>}

        <div className="flex flex-col gap-2">
          <Disclosure
            title="Channels"
            count={status.monitored_channels.length}
            defaultOpen={status.connected && status.monitored_channels.length === 0}
          >
            <ChannelsCard status={status} />
          </Disclosure>
          <Disclosure title="Connection details">
            <dl className="flex flex-col gap-2">
              <Row label="Last event received">
                {status.last_event_at ? formatTime(status.last_event_at) : '–'}
              </Row>
              <Row label="Worker heartbeat">
                {status.heartbeat_at ? formatTime(status.heartbeat_at) : '–'}
              </Row>
            </dl>
            <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
              <Check ok={status.enabled}>Integration enabled</Check>
              <Check ok={status.bot_token_configured && status.app_token_configured}>
                Bot and app tokens set
              </Check>
              <Check ok={status.credentials_verified}>Credentials verified by Slack</Check>
              <Check ok={status.worker_running}>Worker running</Check>
            </ul>
            {status.next_steps.length > 0 && (
              <ol className="mt-3 list-decimal pl-5 text-muted-foreground">
                {status.next_steps.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
            )}
            <p className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              Tokens stay on the backend. Public channels only, no direct messages.
            </p>
          </Disclosure>
          <Disclosure title="Activity">
            <EventsCard />
          </Disclosure>
          <Disclosure title="Setup guide">
            <SetupGuide />
          </Disclosure>
        </div>
      </CardContent>
    </Card>
  )
}

function ChannelsCard({ status }: { status: SlackStatus }) {
  const canQuery = status.bot_token_configured
  const channels = useSlackChannels(canQuery)
  const setChannel = useSetSlackChannel()
  const [manual, setManual] = useState('')

  const addManual = (event: FormEvent) => {
    event.preventDefault()
    const id = manual.trim().toUpperCase()
    if (id) setChannel.mutate({ channelId: id, enabled: true }, { onSuccess: () => setManual('') })
  }

  const list: SlackChannel[] = channels.data
    ? [
        ...channels.data.available,
        ...channels.data.monitored.filter(
          (m) => !channels.data!.available.some((a) => a.channel_id === m.channel_id),
        ),
      ]
    : status.monitored_channels

  return (
    <div className="flex flex-col gap-3 text-sm">
      <p className="text-muted-foreground">
        Only enabled channels are read. Invite the app to a channel first.
      </p>
      {!canQuery && (
        <p className="text-muted-foreground">
          Channel list appears once SLACK_BOT_TOKEN is configured.
        </p>
      )}
      {channels.data?.available_error && canQuery && (
        <Notice tone="warning">{channels.data.available_error}</Notice>
      )}
      {list.length > 0 && (
        <ul className="flex flex-col divide-y rounded-lg border">
          {list.map((c) => (
            <li key={c.channel_id} className="flex flex-wrap items-center gap-2 px-3 py-2">
              <span className="min-w-0 flex-1">
                <span className="font-medium text-foreground">{c.name}</span>
                <span className="ml-2 font-mono text-xs text-muted-foreground">{c.channel_id}</span>
                {c.bot_is_member === false && (
                  <span className="block text-xs text-amber-700">
                    App not in channel: invite it to receive messages
                  </span>
                )}
              </span>
              {c.monitored && <Badge>Monitored</Badge>}
              <Button
                size="sm"
                variant={c.monitored ? 'outline' : 'default'}
                disabled={setChannel.isPending}
                onClick={() =>
                  setChannel.mutate({ channelId: c.channel_id, enabled: !c.monitored })
                }
              >
                {c.monitored ? 'Stop monitoring' : 'Monitor'}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={addManual} className="flex flex-wrap items-center gap-2">
        <input
          value={manual}
          onChange={(e) => setManual(e.target.value)}
          placeholder="Channel ID, e.g. C0123456789"
          aria-label="Channel ID"
          className="h-9 w-64 rounded-lg border bg-background px-3 font-mono text-sm focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
        />
        <Button
          type="submit"
          size="sm"
          variant="outline"
          disabled={!manual.trim() || setChannel.isPending}
        >
          {setChannel.isPending ? (
            <LoaderCircle className="animate-spin" aria-hidden="true" />
          ) : (
            <Plus aria-hidden="true" />
          )}
          Monitor channel
        </Button>
      </form>
      {setChannel.error != null && (
        <Notice tone="error">{getErrorMessage(setChannel.error)}</Notice>
      )}
      <p className="text-xs text-muted-foreground">
        Changing monitored channels is available in development mode only.
      </p>
    </div>
  )
}

function EventsCard() {
  const events = useSlackEvents()
  const level = {
    info: 'text-muted-foreground',
    success: 'text-emerald-700',
    warning: 'text-amber-700',
    error: 'text-red-700',
  }
  return (
    <div>
      {(events.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-muted-foreground">No activity yet.</p>
      ) : (
        <ol className="flex max-h-80 flex-col gap-1.5 overflow-y-auto text-sm">
          {events.data?.map((e) => (
            <li key={e.id} className="flex gap-2">
              <span className="shrink-0 font-mono text-xs text-muted-foreground tabular-nums">
                {new Date(e.created_at).toLocaleTimeString(undefined, {
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
              <span
                className={cn('min-w-0', level[e.level as keyof typeof level] ?? 'text-foreground')}
              >
                {e.message}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

function SetupGuide() {
  return (
    <div>
      <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-sm text-foreground">
        <li>Create an app at api.slack.com/apps (From scratch).</li>
        <li>
          Enable <b>Socket Mode</b> and create an app-level token with{' '}
          <code>connections:write</code>.
        </li>
        <li>
          Bot token scopes: <code>channels:history</code>, <code>channels:read</code>,{' '}
          <code>users:read</code>.
        </li>
        <li>
          Event Subscriptions: subscribe to the bot event <code>message.channels</code>.
        </li>
        <li>Install the app to the workspace and copy the bot token (xoxb-…).</li>
        <li>
          In <code>backend/.env</code>: <code>SLACK_ENABLED=true</code>,{' '}
          <code>SLACK_BOT_TOKEN</code>, <code>SLACK_APP_TOKEN</code>.
        </li>
        <li>
          Run <code>docker compose up -d --force-recreate backend slack-worker</code>.
        </li>
        <li>
          Invite the app to a test channel and click <b>Monitor</b> above.
        </li>
      </ol>
      <p className="mt-3 text-xs text-muted-foreground">
        Full guide: README, section “Slack integration”.
      </p>
    </div>
  )
}
