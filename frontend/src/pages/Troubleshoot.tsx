import {
  ArrowLeft,
  CircleAlert,
  CircleCheck,
  History,
  LoaderCircle,
  NotebookPen,
  Plus,
  ShieldAlert,
  Workflow,
} from 'lucide-react'
import { type FormEvent, type ReactNode, useState } from 'react'
import { useSearchParams } from 'react-router'

import { formatTime } from '@/components/discovery/labels'
import { RecommendationFeedback } from '@/components/feedback/RecommendationFeedback'
import { PageHeader } from '@/components/layout/PageHeader'
import { Tabs } from '@/components/Tabs'
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
    }
  })

  const openSession = (id: string) => {
    setInsufficient(null)
    setSelectedNodeId(null)
    setParams({ session: id })
  }

  const newGuide = () => {
    setInsufficient(null)
    setSelectedNodeId(null)
    setParams({})
  }

  // ---- workspace mode -------------------------------------------------------------------
  if (sessionId) {
    const data = session.data
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title={data?.guide.title ?? 'Guided Troubleshooting'}
          description={
            data
              ? `Problem: “${data.guide.problem_description}”`
              : session.isError
                ? 'This session is not available.'
                : 'Loading session…'
          }
          actions={
            <Button variant="outline" onClick={newGuide}>
              <Plus aria-hidden="true" />
              New guide
            </Button>
          }
        />
        {session.isError && (
          <Notice tone="error">
            {getErrorMessage(session.error)} It may have been removed when the demo data was reset.
            Start a new guide instead.
          </Notice>
        )}
        {session.isPending && <p className="text-sm text-muted-foreground">Loading session…</p>}
        {data && (
          <Workspace session={data} selectedNodeId={selectedNodeId} onSelect={setSelectedNodeId} />
        )}
      </div>
    )
  }

  // ---- start mode -----------------------------------------------------------------------
  return (
    <div className="flex flex-col gap-6">
      <PageHeader />
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="flex flex-col gap-6 lg:col-span-7">
          <ProblemForm
            initialProblem={params.get('problem') ?? ''}
            pending={generate.isPending}
            error={generate.error}
            onSubmit={(problem, equipment) => generate.mutate({ problem, equipment })}
          />
          {insufficient && <InsufficientEvidence guide={insufficient} />}
        </div>
        <div className="flex flex-col gap-6 lg:col-span-5">
          <HowItWorks />
          <RecentSessions onOpen={openSession} />
        </div>
      </div>
    </div>
  )
}

// ---- start mode parts ----------------------------------------------------------------------

function ProblemForm({
  initialProblem,
  pending,
  error,
  onSubmit,
}: {
  initialProblem: string
  pending: boolean
  error: unknown
  onSubmit: (problem: string, equipment?: string) => void
}) {
  const [problem, setProblem] = useState(initialProblem)
  const [equipment, setEquipment] = useState('')
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (problem.trim().length >= 5) onSubmit(problem.trim(), equipment.trim() || undefined)
  }
  return (
    <Card>
      <CardHeader>
        <CardTitle>Describe the problem</CardTitle>
        <CardDescription>
          Plain language is fine. Mention symptoms and what you already tried.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <textarea
            value={problem}
            onChange={(e) => setProblem(e.target.value)}
            rows={4}
            maxLength={1000}
            autoFocus
            aria-label="Problem description"
            placeholder="e.g. customers behind the site router lose their connection every 30 minutes; rebooting did not help"
            className={inputClass}
          />
          <label className="flex flex-col gap-1 text-sm text-muted-foreground sm:w-72">
            Equipment or site (optional)
            <input
              value={equipment}
              onChange={(e) => setEquipment(e.target.value)}
              maxLength={100}
              placeholder="e.g. S17-RTR-02"
              className={cn(inputClass, 'h-9')}
            />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" disabled={pending || problem.trim().length < 5}>
              {pending ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <Workflow aria-hidden="true" />
              )}
              {pending ? 'Building guide… (up to a minute)' : 'Generate guide'}
            </Button>
          </div>
          <div className="flex flex-col gap-1.5 border-t pt-3">
            <span className="text-xs text-muted-foreground">Examples from the demo data</span>
            <div className="flex flex-wrap gap-2">
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
          </div>
          {error != null && <Notice tone="error">{getErrorMessage(error)}</Notice>}
        </form>
      </CardContent>
    </Card>
  )
}

function HowItWorks() {
  const steps = [
    'Finds knowledge colleagues discovered in earlier conversations.',
    'The AI builds a decision tree using only that knowledge.',
    'Every step shows its source messages and approval status.',
    'You answer, take notes and record the outcome. Nothing is executed for you.',
  ]
  return (
    <Card>
      <CardHeader>
        <CardTitle>What happens</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-2.5">
          {steps.map((s, i) => (
            <li key={s} className="flex gap-3 text-sm">
              <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-semibold text-muted-foreground">
                {i + 1}
              </span>
              <span className="text-foreground">{s}</span>
            </li>
          ))}
        </ol>
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
            No steps were generated, so nothing was invented. Use standard diagnostics and escalate
            according to your procedures.
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

function RecentSessions({ onOpen }: { onOpen: (id: string) => void }) {
  const sessions = useRecentSessions()
  const items = sessions.data?.items ?? []
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4" aria-hidden="true" />
          Recent sessions
        </CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sessions yet.</p>
        ) : (
          <ul className="flex flex-col divide-y">
            {items.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onOpen(s.id)}
                  className="flex w-full flex-col gap-1 py-2.5 text-left hover:bg-muted/40"
                >
                  <span className="flex items-center gap-2">
                    <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                      {s.guide_title}
                    </span>
                    <SessionBadge status={s.status} />
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {formatTime(s.updated_at)} · {s.problem_description}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

// ---- workspace -----------------------------------------------------------------------------

function Workspace({
  session,
  selectedNodeId,
  onSelect,
}: {
  session: TroubleshootingSession
  selectedNodeId: string | null
  onSelect: (id: string) => void
}) {
  const guide = session.guide
  const selected =
    guide.nodes.find((n) => n.id === (selectedNodeId ?? session.current_node_id)) ?? null

  return (
    <>
      <div className="flex flex-col gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <SessionBadge status={session.status} />
          <span className="text-muted-foreground">
            Built from {guide.knowledge.length} knowledge item
            {guide.knowledge.length === 1 ? '' : 's'}
            {guide.equipment_identifier && ` · ${guide.equipment_identifier}`} · {guide.model_name}{' '}
            · {formatTime(guide.created_at)}
          </span>
        </div>
        {guide.summary && <p className="text-sm text-foreground">{guide.summary}</p>}
        <p className="flex items-start gap-2 text-xs text-amber-800">
          <ShieldAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {guide.safety_notice}
        </p>
        {(guide.conflicts.length > 0 || guide.uncertainties.length > 0) && (
          <details className="rounded-lg border bg-muted/30 px-3 py-2 text-sm">
            <summary className="cursor-pointer font-medium text-foreground">
              {[
                guide.conflicts.length > 0 &&
                  `${guide.conflicts.length} conflict${guide.conflicts.length === 1 ? '' : 's'} between sources`,
                guide.uncertainties.length > 0 &&
                  `${guide.uncertainties.length} uncertaint${guide.uncertainties.length === 1 ? 'y' : 'ies'}`,
              ]
                .filter(Boolean)
                .join(' · ')}{' '}
              (show)
            </summary>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {guide.conflicts.length > 0 && (
                <ListBox title="Conflicting evidence" items={guide.conflicts} />
              )}
              {guide.uncertainties.length > 0 && (
                <ListBox title="Uncertainties" items={guide.uncertainties} />
              )}
            </div>
          </details>
        )}
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <div className="flex flex-col gap-6 xl:col-span-3">
          <CurrentStep session={session} onSelect={onSelect} />
          <RecommendationFeedback session={session} />
          <NotesAndOutcome session={session} />
        </div>
        <Card className="xl:col-span-6">
          <CardHeader>
            <CardTitle>Decision tree</CardTitle>
            <CardDescription>
              Click a step to see its evidence. Your path is highlighted.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[36rem] w-full overflow-hidden rounded-lg border bg-background">
              <GuideFlow
                guide={guide}
                activePath={session.active_path}
                currentNodeId={session.current_node_id}
                selectedNodeId={selected?.id ?? null}
                onSelect={onSelect}
              />
            </div>
          </CardContent>
        </Card>
        <Card className="xl:col-span-3">
          <CardHeader>
            <CardTitle>Evidence</CardTitle>
            <CardDescription>
              {selected ? `For: ${selected.title}` : 'Select a step'}
            </CardDescription>
          </CardHeader>
          <CardContent className="max-h-[40rem] overflow-y-auto">
            <EvidencePanel guide={guide} node={selected} />
          </CardContent>
        </Card>
      </div>

      <HistoryTimeline session={session} />
    </>
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
  const { step } = useSessionActions(session.id)
  const current = guide.nodes.find((n) => n.id === session.current_node_id) ?? null
  const answers = guide.edges.filter((e) => e.source_node_id === current?.id)
  const open = session.status === 'in_progress'
  const atEnd = current?.node_type === 'resolution' || current?.node_type === 'escalation'

  return (
    <Card className={cn(open && 'ring-2 ring-primary/30')}>
      <CardHeader>
        <CardTitle>{open ? 'Your next step' : 'Final step'}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {current ? (
          <button type="button" onClick={() => onSelect(current.id)} className="text-left">
            <Badge variant="outline">{nodeTypeStyle[current.node_type].label}</Badge>
            <p className="mt-1.5 font-medium text-foreground">{current.title}</p>
            {current.question && <p className="mt-1 text-sm text-foreground">{current.question}</p>}
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
                disabled={step.isPending}
                onClick={() => step.mutate({ type: 'answer', answer_label: edge.answer_label })}
                className="h-auto justify-start py-2 text-left whitespace-normal"
              >
                {edge.answer_label}
                {edge.condition && <span className="text-xs opacity-70"> · {edge.condition}</span>}
              </Button>
            ))}
          </div>
        )}
        {open && atEnd && (
          <p className="text-sm text-muted-foreground">
            End of the guide. Report whether the recommendation worked in “Did it work?”, then
            record the session outcome in “Finish”.
          </p>
        )}
        {open && session.active_path.length > 1 && (
          <Button
            variant="ghost"
            size="sm"
            className="w-fit"
            disabled={step.isPending}
            onClick={() => step.mutate({ type: 'back' })}
          >
            <ArrowLeft aria-hidden="true" />
            Back / revise answer
          </Button>
        )}
        {step.error != null && <Notice tone="error">{getErrorMessage(step.error)}</Notice>}
      </CardContent>
    </Card>
  )
}

function NotesAndOutcome({ session }: { session: TroubleshootingSession }) {
  const { step, complete } = useSessionActions(session.id)
  const [tab, setTab] = useState<'note' | 'finish'>('note')
  const [observation, setObservation] = useState('')
  const [action, setAction] = useState('')
  const [summary, setSummary] = useState('')
  const busy = step.isPending || complete.isPending

  if (session.status !== 'in_progress') {
    return (
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
          <p className="mt-2 text-xs text-muted-foreground">{session.note}</p>
        </CardContent>
      </Card>
    )
  }

  const saveNote = (event: FormEvent) => {
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
    if (summary.trim()) complete.mutate({ outcome, summary: summary.trim() })
  }

  return (
    <Card>
      <CardHeader>
        <Tabs
          label="Notes and outcome"
          value={tab}
          onChange={setTab}
          tabs={[
            { value: 'note', label: 'Add note' },
            { value: 'finish', label: 'Finish' },
          ]}
        />
      </CardHeader>
      <CardContent>
        {tab === 'note' ? (
          <form onSubmit={saveNote} className="flex flex-col gap-2">
            <textarea
              value={observation}
              onChange={(e) => setObservation(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="What did you observe? e.g. lease time shows 60 s"
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
              Save note
            </Button>
            {step.error != null && <Notice tone="error">{getErrorMessage(step.error)}</Notice>}
          </form>
        ) : (
          <div className="flex flex-col gap-2">
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Outcome summary (required)"
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
        )}
      </CardContent>
    </Card>
  )
}

function HistoryTimeline({ session }: { session: TroubleshootingSession }) {
  const nodeTitle = (id: string | null) =>
    session.guide.nodes.find((n) => n.id === id)?.title ?? 'step'
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-4" aria-hidden="true" />
          Session history
        </CardTitle>
        <CardDescription>
          Every answer and note with its time. Revised answers stay visible, crossed out.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {session.steps.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>
        ) : (
          <ol className="relative flex flex-col gap-3 border-l pl-5">
            {session.steps.map((s) => (
              <li
                key={s.id}
                className={cn(
                  'relative text-sm',
                  s.superseded && 'text-muted-foreground line-through',
                )}
              >
                <span className="absolute top-1.5 -left-[25px] size-2.5 rounded-full border-2 border-background bg-primary" />
                <span className="mr-2 font-mono text-xs text-muted-foreground">
                  {new Date(s.created_at).toLocaleTimeString(undefined, {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
                {s.step_type === 'answer' && (
                  <>
                    {nodeTitle(s.node_id)} → <span className="font-medium">{s.answer_label}</span>
                  </>
                )}
                {s.step_type === 'back' && <>Went back to “{nodeTitle(s.node_id)}”</>}
                {s.step_type === 'observation' && <>Note at “{nodeTitle(s.node_id)}”</>}
                {s.step_type === 'complete' && (
                  <span className="font-medium">Session completed</span>
                )}
                {s.observation && (
                  <span className="block text-xs text-muted-foreground">“{s.observation}”</span>
                )}
                {s.action_taken && (
                  <span className="block text-xs text-muted-foreground">
                    Action: {s.action_taken}
                  </span>
                )}
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

// ---- shared ---------------------------------------------------------------------------------

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
    <div className="text-sm">
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
