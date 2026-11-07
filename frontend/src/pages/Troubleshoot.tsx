import {
  ArrowLeft,
  CircleAlert,
  CircleCheck,
  History,
  LoaderCircle,
  NotebookPen,
  Workflow,
} from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useSearchParams } from 'react-router'

import { formatTime } from '@/components/discovery/labels'
import { EvidencePanel } from '@/components/troubleshooting/EvidencePanel'
import { GuideFlow } from '@/components/troubleshooting/GuideFlow'
import { nodeTypeStyle } from '@/components/troubleshooting/nodeStyles'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useGenerateGuide,
  useRecentSessions,
  useSession,
  useSessionActions,
} from '@/hooks/useTroubleshooting'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { Guide, TroubleshootingSession } from '@/types/api'

const EXAMPLES = [
  'Customers keep losing their connection every half hour, rebooting the router did not help',
  'BGP neighbor keeps going down with hold timer expired',
]

const inputClass =
  'w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none'

export default function Troubleshoot() {
  const [params, setParams] = useSearchParams()
  const sessionId = params.get('session')
  const [insufficient, setInsufficient] = useState<Guide | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  const session = useSession(sessionId)
  const generate = useGenerateGuide((guide, started) => {
    setSelectedNodeId(null)
    if (started) {
      setInsufficient(null)
      setParams({ session: started.id })
    } else {
      setInsufficient(guide)
      setParams({})
    }
  })

  const openSession = (id: string) => {
    setInsufficient(null)
    setSelectedNodeId(null)
    setParams({ session: id })
  }

  const data = session.data
  const guide = data?.guide
  const selected =
    guide?.nodes.find((n) => n.id === (selectedNodeId ?? data?.current_node_id)) ?? null

  return (
    <div className="flex flex-col gap-6">
      <ProblemForm
        pending={generate.isPending}
        error={generate.error}
        onSubmit={(problem, equipment) => generate.mutate({ problem, equipment })}
      />

      {insufficient && <InsufficientEvidence guide={insufficient} />}

      {sessionId && session.isPending && (
        <p className="text-sm text-muted-foreground">Loading session…</p>
      )}
      {session.isError && <Notice tone="error">{getErrorMessage(session.error)}</Notice>}

      {data && guide && (
        <>
          <GuideHeader session={data} />
          <div className="grid gap-6 xl:grid-cols-12">
            <div className="flex flex-col gap-6 xl:col-span-3">
              <CurrentStep session={data} onSelect={setSelectedNodeId} />
            </div>
            <Card className="xl:col-span-6">
              <CardHeader>
                <CardTitle>Decision tree</CardTitle>
                <CardDescription>
                  Click a step to see its evidence. The highlighted path is the one you took.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="h-[34rem] w-full overflow-hidden rounded-lg border bg-background">
                  <GuideFlow
                    guide={guide}
                    activePath={data.active_path}
                    currentNodeId={data.current_node_id}
                    selectedNodeId={selected?.id ?? null}
                    onSelect={setSelectedNodeId}
                  />
                </div>
              </CardContent>
            </Card>
            <Card className="xl:col-span-3">
              <CardHeader>
                <CardTitle>Evidence</CardTitle>
                <CardDescription>Sources behind the selected step</CardDescription>
              </CardHeader>
              <CardContent className="max-h-[42rem] overflow-y-auto">
                <EvidencePanel guide={guide} node={selected} />
              </CardContent>
            </Card>
          </div>
        </>
      )}

      <RecentSessions currentId={sessionId} onOpen={openSession} />
    </div>
  )
}

function ProblemForm({
  pending,
  error,
  onSubmit,
}: {
  pending: boolean
  error: unknown
  onSubmit: (problem: string, equipment?: string) => void
}) {
  const [problem, setProblem] = useState('')
  const [equipment, setEquipment] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (problem.trim().length >= 5) onSubmit(problem.trim(), equipment.trim() || undefined)
  }
  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Guided troubleshooting</h2>
          <p className="text-sm text-muted-foreground">
            Describe the problem. Elisa Echo finds knowledge your colleagues discovered in earlier
            conversations and builds a step-by-step guide from it. Every step shows its sources;
            nothing is executed for you.
          </p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm text-muted-foreground">
            Problem description
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              rows={2}
              maxLength={1000}
              placeholder="e.g. customers behind the site router lose their connection every 30 minutes"
              className={inputClass}
            />
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex flex-col gap-1 text-sm text-muted-foreground sm:w-64">
              Equipment or site (optional)
              <input
                value={equipment}
                onChange={(e) => setEquipment(e.target.value)}
                maxLength={100}
                placeholder="e.g. S17-RTR-02"
                className={cn(inputClass, 'h-9')}
              />
            </label>
            <Button type="submit" disabled={pending || problem.trim().length < 5}>
              {pending ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <Workflow aria-hidden="true" />
              )}
              {pending ? 'Searching knowledge and building guide…' : 'Generate guide'}
            </Button>
          </div>
        </form>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">Try:</span>
          {EXAMPLES.map((example) => (
            <button
              key={example}
              type="button"
              onClick={() => setProblem(example)}
              className="rounded-full border bg-muted/40 px-3 py-1 text-left text-xs text-foreground hover:bg-accent"
            >
              {example}
            </button>
          ))}
        </div>
        {error != null && <Notice tone="error">{getErrorMessage(error)}</Notice>}
      </CardContent>
    </Card>
  )
}

function InsufficientEvidence({ guide }: { guide: Guide }) {
  return (
    <Card>
      <CardContent className="flex items-start gap-3">
        <CircleAlert className="mt-0.5 size-5 shrink-0 text-amber-600" aria-hidden="true" />
        <div className="text-sm">
          <p className="font-medium text-foreground">Not enough evidence for a guide</p>
          <p className="mt-1 text-muted-foreground">{guide.status_reason}</p>
          <p className="mt-2 text-muted-foreground">
            No steps were generated, so nothing was invented. Verify the problem with standard
            diagnostics and escalate according to your procedures.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

function GuideHeader({ session }: { session: TroubleshootingSession }) {
  const guide = session.guide
  return (
    <Card>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold text-foreground">{guide.title}</h2>
            {guide.summary && <p className="text-sm text-muted-foreground">{guide.summary}</p>}
            <p className="mt-1 text-xs text-muted-foreground">
              Problem: “{guide.problem_description}”
              {guide.equipment_identifier && ` · ${guide.equipment_identifier}`} · based on{' '}
              {guide.knowledge.length} knowledge item{guide.knowledge.length === 1 ? '' : 's'} ·{' '}
              {guide.model_name}
            </p>
          </div>
          <SessionBadge status={session.status} />
        </div>
        <Notice tone="warning">{guide.safety_notice}</Notice>
        {(guide.conflicts.length > 0 || guide.uncertainties.length > 0) && (
          <div className="grid gap-3 sm:grid-cols-2">
            {guide.conflicts.length > 0 && (
              <ListBox title="Conflicting evidence" items={guide.conflicts} />
            )}
            {guide.uncertainties.length > 0 && (
              <ListBox title="Uncertainties" items={guide.uncertainties} />
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function CurrentStep({
  session,
  onSelect,
}: {
  session: TroubleshootingSession
  onSelect: (id: string) => void
}) {
  const guide = session.guide
  const { step, complete } = useSessionActions(session.id)
  const [observation, setObservation] = useState('')
  const [action, setAction] = useState('')
  const [summary, setSummary] = useState('')
  const current = guide.nodes.find((n) => n.id === session.current_node_id) ?? null
  const answers = guide.edges.filter((e) => e.source_node_id === current?.id)
  const open = session.status === 'in_progress'
  const atEnd = current?.node_type === 'resolution' || current?.node_type === 'escalation'
  const nodeTitle = (id: string | null) => guide.nodes.find((n) => n.id === id)?.title ?? 'step'
  const busy = step.isPending || complete.isPending

  const saveObservation = (event: FormEvent) => {
    event.preventDefault()
    if (!observation.trim() && !action.trim()) return
    step.mutate(
      {
        type: 'observation',
        observation: observation.trim() || undefined,
        action_taken: action.trim() || undefined,
      },
      {
        onSuccess: () => {
          setObservation('')
          setAction('')
        },
      },
    )
  }

  const finish = (outcome: 'resolved' | 'unresolved') => {
    if (!summary.trim()) return
    complete.mutate({ outcome, summary: summary.trim(), action_taken: action.trim() || undefined })
  }

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Current step</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {current ? (
            <button type="button" onClick={() => onSelect(current.id)} className="text-left">
              <Badge variant="outline">{nodeTypeStyle[current.node_type].label}</Badge>
              <p className="mt-1.5 font-medium text-foreground">{current.title}</p>
              {current.question && (
                <p className="mt-1 text-sm text-foreground">{current.question}</p>
              )}
              {current.description && (
                <p className="mt-1 text-sm text-muted-foreground">{current.description}</p>
              )}
            </button>
          ) : (
            <p className="text-sm text-muted-foreground">No current step.</p>
          )}

          {open && !atEnd && answers.length > 0 && (
            <div className="flex flex-col gap-2">
              {answers.map((edge) => (
                <Button
                  key={edge.id}
                  variant={answers.length === 1 ? 'default' : 'outline'}
                  disabled={busy}
                  onClick={() => step.mutate({ type: 'answer', answer_label: edge.answer_label })}
                  className="h-auto justify-start py-2 text-left whitespace-normal"
                >
                  {edge.answer_label}
                  {edge.condition && (
                    <span className="text-xs opacity-70"> · {edge.condition}</span>
                  )}
                </Button>
              ))}
            </div>
          )}
          {open && atEnd && (
            <p className="text-sm text-muted-foreground">
              End of the guide. Record what you did and complete the session below.
            </p>
          )}
          {open && session.active_path.length > 1 && (
            <Button
              variant="ghost"
              size="sm"
              className="w-fit"
              disabled={busy}
              onClick={() => step.mutate({ type: 'back' })}
            >
              <ArrowLeft aria-hidden="true" />
              Back / revise previous answer
            </Button>
          )}
          {step.error != null && <Notice tone="error">{getErrorMessage(step.error)}</Notice>}
        </CardContent>
      </Card>

      {open ? (
        <Card>
          <CardHeader>
            <CardTitle>Record</CardTitle>
            <CardDescription>Saved with a timestamp at the current step</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <form onSubmit={saveObservation} className="flex flex-col gap-2">
              <textarea
                value={observation}
                onChange={(e) => setObservation(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Observation, e.g. lease time shows 60 s"
                className={inputClass}
                aria-label="Observation"
              />
              <input
                value={action}
                onChange={(e) => setAction(e.target.value)}
                maxLength={500}
                placeholder="Action you took (optional)"
                className={cn(inputClass, 'h-9')}
                aria-label="Action taken"
              />
              <Button
                type="submit"
                variant="outline"
                size="sm"
                className="w-fit"
                disabled={busy || (!observation.trim() && !action.trim())}
              >
                <NotebookPen aria-hidden="true" />
                Save observation
              </Button>
            </form>
            <div className="flex flex-col gap-2 border-t pt-3">
              <textarea
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                rows={2}
                maxLength={2000}
                placeholder="Outcome summary (required to complete)"
                className={inputClass}
                aria-label="Outcome summary"
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  disabled={busy || !summary.trim()}
                  onClick={() => finish('resolved')}
                >
                  <CircleCheck aria-hidden="true" />
                  Resolved
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !summary.trim()}
                  onClick={() => finish('unresolved')}
                >
                  Not resolved
                </Button>
              </div>
              {complete.error != null && (
                <Notice tone="error">{getErrorMessage(complete.error)}</Notice>
              )}
              <p className="text-xs text-muted-foreground">{session.note}</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Outcome</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 text-sm">
            <SessionBadge status={session.status} />
            <p className="mt-1 text-foreground">{session.outcome_summary}</p>
            {session.action_taken && (
              <p className="text-muted-foreground">Action: {session.action_taken}</p>
            )}
            <p className="text-xs text-muted-foreground">
              Completed {formatTime(session.completed_at)}
            </p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>History</CardTitle>
        </CardHeader>
        <CardContent>
          {session.steps.length === 0 ? (
            <p className="text-sm text-muted-foreground">No steps recorded yet.</p>
          ) : (
            <ol className="flex flex-col gap-2 text-sm">
              {session.steps.map((s) => (
                <li
                  key={s.id}
                  className={cn('flex gap-2', s.superseded && 'text-muted-foreground line-through')}
                >
                  <span className="shrink-0 font-mono text-xs text-muted-foreground">
                    {new Date(s.created_at).toLocaleTimeString(undefined, {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                  <span className="min-w-0">
                    {s.step_type === 'answer' && (
                      <>
                        {nodeTitle(s.node_id)}:{' '}
                        <span className="font-medium">{s.answer_label}</span>
                      </>
                    )}
                    {s.step_type === 'back' && <>Went back to {nodeTitle(s.node_id)}</>}
                    {s.step_type === 'observation' && <>Observation at {nodeTitle(s.node_id)}</>}
                    {s.step_type === 'complete' && <>Session completed</>}
                    {s.observation && (
                      <span className="block text-xs text-muted-foreground">“{s.observation}”</span>
                    )}
                    {s.action_taken && (
                      <span className="block text-xs text-muted-foreground">
                        Action: {s.action_taken}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </>
  )
}

function RecentSessions({
  currentId,
  onOpen,
}: {
  currentId: string | null
  onOpen: (id: string) => void
}) {
  const sessions = useRecentSessions()
  const items = sessions.data?.items ?? []
  if (items.length === 0) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4" aria-hidden="true" />
          Recent sessions
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col divide-y">
          {items.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => onOpen(s.id)}
                className={cn(
                  'flex w-full flex-wrap items-center gap-2 py-2 text-left text-sm hover:bg-muted/40',
                  s.id === currentId && 'font-medium',
                )}
              >
                <span className="min-w-0 flex-1 truncate text-foreground">{s.guide_title}</span>
                <span className="truncate text-xs text-muted-foreground sm:max-w-xs">
                  {s.problem_description}
                </span>
                <SessionBadge status={s.status} />
                <span className="text-xs text-muted-foreground">{formatTime(s.updated_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function SessionBadge({ status }: { status: TroubleshootingSession['status'] }) {
  const label = { in_progress: 'In progress', resolved: 'Resolved', unresolved: 'Not resolved' }[
    status
  ]
  return (
    <Badge
      variant={
        status === 'resolved' ? 'default' : status === 'unresolved' ? 'destructive' : 'secondary'
      }
    >
      {label}
    </Badge>
  )
}

function ListBox({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-lg border bg-muted/40 p-3 text-sm">
      <p className="mb-1 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </p>
      <ul className="list-disc pl-5 text-foreground">
        {items.map((i) => (
          <li key={i}>{i}</li>
        ))}
      </ul>
    </div>
  )
}

function Notice({ tone, children }: { tone: 'warning' | 'error'; children: ReactNode }) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-2 rounded-lg border px-3 py-2 text-sm',
        tone === 'error'
          ? 'border-red-200 bg-red-50 text-red-800'
          : 'border-amber-200 bg-amber-50 text-amber-900',
      )}
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  )
}
