import { CircleAlert, CircleCheck, Link2, Pause, Play, RefreshCw, Unplug } from 'lucide-react'
import { type FormEvent, useState } from 'react'

import { formatTime } from '@/components/discovery/labels'
import { Button } from '@/components/ui/button'
import { useEmailConnections, useMailboxActions } from '@/hooks/useSources'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { EmailCheckResult, EmailConnection } from '@/types/api'

const inputClass =
  'h-9 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none'

/** Connect a real mailbox folder over IMAP (read-only) and watch it being read. */
export function MailboxConnect() {
  const connections = useEmailConnections()
  const list = connections.data ?? []
  return (
    <div className="flex flex-col gap-3">
      {list.map((c) => (
        <ConnectionRow key={c.id} connection={c} />
      ))}
      <ConnectForm compact={list.length > 0} />
    </div>
  )
}

function ConnectionRow({ connection: c }: { connection: EmailConnection }) {
  const { check, toggle, disconnect } = useMailboxActions()
  const [result, setResult] = useState<EmailCheckResult | null>(null)
  const ok = c.status === 'connected' && !c.last_error
  return (
    <div className="flex flex-col gap-2 rounded-lg border px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-1.5">
          {ok ? (
            <CircleCheck className="size-4 text-emerald-700" aria-hidden="true" />
          ) : (
            <CircleAlert className="size-4 text-amber-700" aria-hidden="true" />
          )}
          <span className="font-mono text-xs">{c.username}</span>
          <span className="text-xs text-muted-foreground">· folder “{c.folder}”</span>
        </span>
        <span className="text-xs text-muted-foreground">
          {c.enabled ? 'Checked every minute' : 'Paused'}
          {c.last_checked_at && ` · last ${formatTime(c.last_checked_at)}`}
        </span>
      </div>
      <p className="text-xs text-muted-foreground">
        {c.imported_count} email(s) imported
        {c.folder_message_count != null && ` · ${c.folder_message_count} in the folder`} ·
        read-only, emails from the last {c.since_days} day(s) on the first check, max{' '}
        {c.max_per_poll} per check
      </p>
      {c.last_error && <p className="text-xs text-red-700">{c.last_error}</p>}
      {result && (
        <p className="text-xs text-muted-foreground">
          {result.error ??
            `${result.imported} new, ${result.duplicates} already known` +
              (result.remaining ? `, ${result.remaining} more next time` : '') +
              (result.threads.length ? ` · analyzing: ${result.threads.join('; ')}` : '')}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={check.isPending || !c.enabled}
          onClick={() => check.mutate(c.id, { onSuccess: setResult })}
        >
          <RefreshCw className={cn(check.isPending && 'animate-spin')} aria-hidden="true" />
          Check now
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={toggle.isPending}
          onClick={() => toggle.mutate({ id: c.id, enabled: !c.enabled })}
        >
          {c.enabled ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
          {c.enabled ? 'Pause' : 'Resume'}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={disconnect.isPending}
          onClick={() => disconnect.mutate(c.id)}
        >
          <Unplug aria-hidden="true" />
          Disconnect
        </Button>
      </div>
      {check.error != null && (
        <p className="text-xs text-red-700">{getErrorMessage(check.error)}</p>
      )}
    </div>
  )
}

function ConnectForm({ compact }: { compact: boolean }) {
  const { connect } = useMailboxActions()
  const [open, setOpen] = useState(!compact)
  const [host, setHost] = useState('imap.gmail.com')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [folder, setFolder] = useState('Elisa Echo')
  const [sinceDays, setSinceDays] = useState(3)
  const [maxPerPoll, setMaxPerPoll] = useState(10)

  if (!open) {
    return (
      <Button size="sm" variant="outline" className="w-fit" onClick={() => setOpen(true)}>
        <Link2 aria-hidden="true" />
        Connect another mailbox
      </Button>
    )
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    connect.mutate(
      {
        host,
        port: 993,
        username,
        password,
        folder,
        since_days: sinceDays,
        max_per_poll: maxPerPoll,
      },
      {
        onSuccess: () => {
          setPassword('')
          if (compact) setOpen(false)
        },
      },
    )
  }

  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-2 rounded-lg border bg-muted/20 p-3"
      aria-label="Connect a mailbox"
    >
      <p className="font-medium text-foreground">Connect your mailbox (IMAP)</p>
      <div className="grid gap-2 sm:grid-cols-2">
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          type="email"
          required
          placeholder="you@gmail.com"
          aria-label="Email address"
          autoComplete="username"
          className={inputClass}
        />
        <input
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          type="password"
          required
          placeholder="App password (16 characters)"
          aria-label="App password"
          autoComplete="off"
          className={inputClass}
        />
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Folder or Gmail label to read
          <input
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            required
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          IMAP server
          <input
            value={host}
            onChange={(e) => setHost(e.target.value)}
            required
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          First check: emails from the last … days
          <input
            type="number"
            min={1}
            max={30}
            value={sinceDays}
            onChange={(e) => setSinceDays(Number(e.target.value))}
            className={inputClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Max emails per check (each = one Gemini call)
          <input
            type="number"
            min={1}
            max={50}
            value={maxPerPoll}
            onChange={(e) => setMaxPerPoll(Number(e.target.value))}
            className={inputClass}
          />
        </label>
      </div>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer hover:text-foreground">
          How to get a Gmail app password
        </summary>
        <ol className="mt-1 list-decimal pl-5">
          <li>Turn on 2-Step Verification for your Google account.</li>
          <li>
            Open myaccount.google.com/apppasswords, create one named “Elisa Echo”, copy the
            16-character password.
          </li>
          <li>
            In Gmail create a label “Elisa Echo” and put (or filter) the work emails you want read
            into it. Using INBOX reads all new mail instead.
          </li>
        </ol>
      </details>
      <p className="text-xs text-muted-foreground">
        Read-only: emails are never changed or marked as read. The password is stored encrypted on
        the server, never shown again, and deleted when you disconnect. Email text is sent to Gemini
        for analysis.
      </p>
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={connect.isPending || !username || !password}>
          <Link2 aria-hidden="true" />
          {connect.isPending ? 'Checking login…' : 'Connect'}
        </Button>
        {compact && (
          <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        )}
      </div>
      {connect.error != null && (
        <p className="text-sm text-red-700">{getErrorMessage(connect.error)}</p>
      )}
    </form>
  )
}
