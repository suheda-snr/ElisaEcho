import {
  ArrowLeft,
  CircleCheck,
  GitBranch,
  History,
  ListOrdered,
  LoaderCircle,
  NotebookPen,
  Plus,
  ShieldAlert,
  TriangleAlert,
  Workflow,
} from 'lucide-react'
import { type FormEvent, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { Disclosure } from '@/components/common/Disclosure'
import { EmptyState, Loading, Notice } from '@/components/common/States'
import { formatTime } from '@/components/discovery/labels'
import { RecommendationFeedback, StepFeedback } from '@/components/feedback/RecommendationFeedback'
import { PageHeader } from '@/components/layout/PageHeader'
import { EvidencePanel } from '@/components/troubleshooting/EvidencePanel'
import { GuideFlow } from '@/components/troubleshooting/GuideFlow'
import { nodeTypeStyle, supportStyle } from '@/components/troubleshooting/nodeStyles'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  useGenerateGuide,
  useRecentSessions,
  useSession,
  useSessionActions,
} from '@/hooks/useTroubleshooting'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { Guide, GuideNode, TroubleshootingSession } from '@/types/api'

const EXAMPLES = [
  'TRN-118: replaced the SFP, interface is up and optics are normal, but traffic does not recover',
  'Customers keep losing their connection every half hour, rebooting the router did not help',
]

const inputClass =
  'w-full rounded-lg border bg-background px-3 py-2 text-[15px] text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none'

type View = 'steps' | 'tree'

export default function Troubleshoot() {
  const [params, setParams] = useSearchParams()
  const sessionId = params.get('session')
  const [insufficient, setInsufficient] = useState<Guide | null>(null)
  const session = useSession(sessionId)

  const generate = useGenerateGuide((guide, started) => {
    if (started) {
      setInsufficient(null)
      setParams({ session: started.id })
    } else {
      setInsufficient(guide)
    }
  })

  const openSession = (id: string) => {
    setInsufficient(null)
    setParams({ session: id })
  }

  if (sessionId) {
    const data = session.data
    return (
      <div className="flex flex-col gap-5">
        <PageHeader
          title={data?.guide.title ?? 'Troubleshooting'}
          description={data ? `“${data.guide.problem_description}”` : undefined}
          actions={
            <Button variant="outline" onClick={() => setParams({})}>
              <Plus aria-hidden="true" />
              New guide
            </Button>
          }
        />
        {session.isError && (
          <Notice tone="error">
            {getErrorMessage(session.error)} The session may have been removed with the demo data.
            Start a new guide instead.
          </Notice>
        )}
        {session.isPending && <Loading label="Loading session…" />}
        {data && (
          <Workspace
            session={data}
            initialView={params.get('view') === 'tree' ? 'tree' : 'steps'}
          />
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader />
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="flex flex-col gap-4 lg:col-span-7">
          <ProblemForm
            initialProblem={params.get('problem') ?? ''}
            initialEquipment={params.get('equipment') ?? ''}
            pending={generate.isPending}
            error={generate.error}
            onSubmit={(problem, equipment) => generate.mutate({ problem, equipment })}
          />
          {insufficient && (
            <Notice tone="warning">
              <span className="font-medium">Not enough evidence for a guide.</span>{' '}
              {insufficient.status_reason} No steps were invented; follow your standard procedures.
            </Notice>
          )}
        </div>
        <div className="lg:col-span-5">
          <RecentSessions onOpen={openSession} />
        </div>
      </div>
    </div>
  )
}

// ---- start --------------------------------------------------------------------------------------

function ProblemForm({
  initialProblem,
  initialEquipment,
  pending,
  error,
  onSubmit,
}: {
  initialProblem: string
  initialEquipment: string
  pending: boolean
  error: unknown
  onSubmit: (problem: string, equipment?: string) => void
}) {
  const [problem, setProblem] = useState(initialProblem)
  const [equipment, setEquipment] = useState(initialEquipment)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (problem.trim().length >= 5) onSubmit(problem.trim(), equipment.trim() || undefined)
  }
  return (
    <Card>
      <CardContent>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">What is happening?</span>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              rows={4}
              maxLength={1000}
              autoFocus
              placeholder="Symptoms, the node or site, and what you already tried"
              className={inputClass}
            />
          </label>
          <label className="flex flex-col gap-1.5 sm:w-80">
            <span className="text-sm font-medium text-foreground">
              Equipment or site{' '}
              <span className="font-normal text-muted-foreground">(optional)</span>
            </span>
            <input
              value={equipment}
              onChange={(e) => setEquipment(e.target.value)}
              maxLength={100}
              placeholder="e.g. TRN-118"
              className={cn(inputClass, 'h-10')}
            />
          </label>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="lg" disabled={pending || problem.trim().length < 5}>
              {pending ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : (
                <Workflow aria-hidden="true" />
              )}
              {pending ? 'Building guide…' : 'Generate guide'}
            </Button>
            {pending && (
              <span className="text-sm text-muted-foreground">This can take up to a minute.</span>
            )}
          </div>
          {!problem && (
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setProblem(example)}
                  className="rounded-full border bg-background px-3 py-1 text-left text-sm text-foreground hover:bg-accent"
                >
                  {example}
                </button>
              ))}
            </div>
          )}
          {error != null && <Notice tone="error">{getErrorMessage(error)}</Notice>}
        </form>
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
        {sessions.isPending ? (
          <Loading />
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sessions yet.</p>
        ) : (
          <ul className="-my-1 flex flex-col divide-y">
            {items.slice(0, 8).map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => onOpen(s.id)}
                  className="flex w-full flex-col gap-0.5 rounded-md px-1 py-2.5 text-left hover:bg-muted/50"
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

// ---- workspace ----------------------------------------------------------------------------------

function Workspace({
  session,
  initialView,
}: {
  session: TroubleshootingSession
  initialView: View
}) {
  const guide = session.guide
  const [view, setView] = useState<View>(initialView)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const issues = guide.conflicts.length + guide.uncertainties.length

  return (
    <>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <SessionBadge status={session.status} />
        <span className="text-sm text-muted-foreground">
          From {guide.knowledge.length} knowledge item{guide.knowledge.length === 1 ? '' : 's'}
          {guide.equipment_identifier && ` · ${guide.equipment_identifier}`}
        </span>
        <span className="inline-flex items-center gap-1.5 text-sm text-amber-800">
          <ShieldAlert className="size-4" aria-hidden="true" />
          Decision support: nothing is executed for you
        </span>
        <div role="tablist" aria-label="View" className="ml-auto flex rounded-lg bg-muted p-1">
          {(
            [
              ['steps', 'Step-by-step', ListOrdered],
              ['tree', 'Decision tree', GitBranch],
            ] as const
          ).map(([value, label, Icon]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={view === value}
              onClick={() => setView(value)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                view === value
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {issues > 0 && (
        <Disclosure
          title={
            <span className="inline-flex items-center gap-2 text-amber-900">
              <TriangleAlert className="size-4" aria-hidden="true" />
              {[
                guide.conflicts.length > 0 &&
                  `${guide.conflicts.length} conflict${guide.conflicts.length === 1 ? '' : 's'} between sources`,
                guide.uncertainties.length > 0 &&
                  `${guide.uncertainties.length} open question${guide.uncertainties.length === 1 ? '' : 's'}`,
              ]
                .filter(Boolean)
                .join(' · ')}
            </span>
          }
          className="border-amber-200"
        >
          <ul className="flex flex-col gap-1 text-sm text-foreground">
            {[...guide.conflicts, ...guide.uncertainties].map((c) => (
              <li key={c}>· {c}</li>
            ))}
          </ul>
        </Disclosure>
      )}

      {view === 'steps' ? (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="flex flex-col gap-4 lg:col-span-8">
            {session.status === 'in_progress' ? (
              <CurrentStep session={session} />
            ) : (
              <Completed session={session} />
            )}
          </div>
          <div className="flex flex-col gap-4 lg:col-span-4">
            <PathCard session={session} />
            <Disclosure title="Session history" count={session.steps.length}>
              <HistoryTimeline session={session} />
            </Disclosure>
          </div>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="lg:col-span-8">
            <GuideFlow
              guide={guide}
              activePath={session.active_path}
              currentNodeId={session.current_node_id}
              selectedNodeId={selectedNodeId ?? session.current_node_id}
              onSelect={setSelectedNodeId}
            />
            <p className="mt-2 text-sm text-muted-foreground">
              Your path is highlighted. Select a step to see why it is there.
            </p>
          </div>
          <Card className="lg:col-span-4">
            <CardContent className="max-h-[46rem] overflow-y-auto">
              <EvidencePanel
                guide={guide}
                node={
                  guide.nodes.find((n) => n.id === (selectedNodeId ?? session.current_node_id)) ??
                  null
                }
              />
            </CardContent>
          </Card>
        </div>
      )}
    </>
  )
}

function StepHeader({ node, index }: { node: GuideNode; index: number }) {
  const style = nodeTypeStyle[node.node_type]
  const support = supportStyle[node.support_level]
  const Icon = style.icon
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-sm text-muted-foreground">Step {index}</span>
      <span
        className={cn(
          'inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium',
          style.chip,
        )}
      >
        <Icon className="size-3.5" aria-hidden="true" />
        {style.label}
      </span>
      {support && (
        <span
          className={cn('rounded-full border px-2 py-0.5 text-xs font-medium', support.className)}
        >
          {support.label}
        </span>
      )}
    </div>
  )
}

function CurrentStep({ session }: { session: TroubleshootingSession }) {
  const guide = session.guide
  const { step } = useSessionActions(session.id)
  const node = guide.nodes.find((n) => n.id === session.current_node_id) ?? null
  if (!node) {
    return <EmptyState icon={Workflow} title="This session has no current step" />
  }
  const answers = guide.edges.filter((e) => e.source_node_id === node.id)
  const atEnd = node.node_type === 'resolution' || node.node_type === 'escalation'
  const actionStep = node.node_type === 'recommendation' || node.node_type === 'resolution'

  return (
    <Card className="ring-1 ring-primary/20">
      <CardContent className="flex flex-col gap-5">
        <div className="flex flex-col gap-2">
          <StepHeader node={node} index={session.active_path.length} />
          <h2 className="text-2xl leading-tight font-semibold text-foreground">{node.title}</h2>
          {node.question && <p className="text-lg text-foreground">{node.question}</p>}
          {node.description && (
            <p className="text-[15px] leading-relaxed text-foreground/80">{node.description}</p>
          )}
        </div>

        {node.conflict_note && <Notice tone="warning">{node.conflict_note}</Notice>}
        {node.requires_manual_verification && (
          <p className="flex items-center gap-1.5 text-sm text-amber-800">
            <ShieldAlert className="size-4 shrink-0" aria-hidden="true" />
            Not an approved procedure: check it applies and follow your change process.
          </p>
        )}

        {!atEnd && answers.length > 0 && (
          <div className="grid gap-2 sm:grid-cols-2">
            {answers.map((edge) => (
              <Button
                key={edge.id}
                size="lg"
                variant={answers.length === 1 ? 'default' : 'outline'}
                disabled={step.isPending}
                onClick={() => step.mutate({ type: 'answer', answer_label: edge.answer_label })}
                className="h-auto min-h-12 justify-start py-3 text-left text-[15px] whitespace-normal"
              >
                <span className="flex flex-col items-start">
                  {edge.answer_label}
                  {edge.condition && (
                    <span className="text-xs font-normal opacity-75">{edge.condition}</span>
                  )}
                </span>
              </Button>
            ))}
          </div>
        )}
        {step.error != null && <Notice tone="error">{getErrorMessage(step.error)}</Notice>}

        {actionStep && (
          <div className="rounded-xl border bg-muted/30 p-4">
            <p className="mb-3 font-medium text-foreground">
              {atEnd ? 'Did this resolve the problem?' : 'After trying it: did it work?'}
            </p>
            <StepFeedback session={session} node={node} />
          </div>
        )}

        {atEnd && <FinishSession session={session} />}

        <div className="flex flex-col gap-2">
          <Disclosure title="Why this step?">
            <EvidencePanel guide={guide} node={node} />
          </Disclosure>
          <Disclosure title="Add a note">
            <NoteForm session={session} />
          </Disclosure>
        </div>

        {session.active_path.length > 1 && (
          <Button
            variant="ghost"
            size="sm"
            className="w-fit"
            disabled={step.isPending}
            onClick={() => step.mutate({ type: 'back' })}
          >
            <ArrowLeft aria-hidden="true" />
            Back to previous step
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function NoteForm({ session }: { session: TroubleshootingSession }) {
  const { step } = useSessionActions(session.id)
  const [observation, setObservation] = useState('')
  const [action, setAction] = useState('')
  const save = (event: FormEvent) => {
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
  return (
    <form onSubmit={save} className="flex flex-col gap-2">
      <textarea
        value={observation}
        onChange={(e) => setObservation(e.target.value)}
        rows={2}
        maxLength={2000}
        placeholder="What did you observe? e.g. counters stay at zero"
        className={inputClass}
        aria-label="Observation"
      />
      <input
        value={action}
        onChange={(e) => setAction(e.target.value)}
        maxLength={500}
        placeholder="Action you took (optional)"
        className={cn(inputClass, 'h-10')}
        aria-label="Action taken"
      />
      <Button
        type="submit"
        variant="outline"
        size="sm"
        className="w-fit"
        disabled={step.isPending || (!observation.trim() && !action.trim())}
      >
        <NotebookPen aria-hidden="true" />
        Save note
      </Button>
      {step.isSuccess && <p className="text-sm text-emerald-800">Saved to the session history.</p>}
      {step.error != null && <Notice tone="error">{getErrorMessage(step.error)}</Notice>}
    </form>
  )
}

function FinishSession({ session }: { session: TroubleshootingSession }) {
  const { complete } = useSessionActions(session.id)
  const [summary, setSummary] = useState('')
  const finish = (outcome: 'resolved' | 'unresolved') => {
    if (summary.trim()) complete.mutate({ outcome, summary: summary.trim() })
  }
  return (
    <div className="flex flex-col gap-2 rounded-xl border p-4">
      <p className="font-medium text-foreground">Finish the session</p>
      <textarea
        value={summary}
        onChange={(e) => setSummary(e.target.value)}
        rows={2}
        maxLength={2000}
        placeholder="Short outcome summary (required)"
        className={inputClass}
        aria-label="Outcome summary"
      />
      <div className="flex flex-wrap gap-2">
        <Button disabled={complete.isPending || !summary.trim()} onClick={() => finish('resolved')}>
          <CircleCheck aria-hidden="true" />
          Problem resolved
        </Button>
        <Button
          variant="outline"
          disabled={complete.isPending || !summary.trim()}
          onClick={() => finish('unresolved')}
        >
          Not resolved
        </Button>
      </div>
      {complete.error != null && <Notice tone="error">{getErrorMessage(complete.error)}</Notice>}
    </div>
  )
}

function Completed({ session }: { session: TroubleshootingSession }) {
  return (
    <>
      <Card>
        <CardContent className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <SessionBadge status={session.status} />
            <span className="text-sm text-muted-foreground">
              Completed {formatTime(session.completed_at)}
            </span>
          </div>
          <p className="text-[15px] text-foreground">{session.outcome_summary}</p>
          {session.action_taken && (
            <p className="text-sm text-muted-foreground">Action: {session.action_taken}</p>
          )}
          <Link to="/troubleshoot" className="text-sm font-medium text-primary hover:underline">
            Start a new guide
          </Link>
        </CardContent>
      </Card>
      <RecommendationFeedback session={session} />
    </>
  )
}

function PathCard({ session }: { session: TroubleshootingSession }) {
  const guide = session.guide
  const answers = session.steps.filter((s) => s.step_type === 'answer' && !s.superseded)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Your path</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="flex flex-col gap-2.5">
          {session.active_path.map((id, i) => {
            const node = guide.nodes.find((n) => n.id === id)
            const answer = answers.find((a) => a.node_id === id)
            const current = id === session.current_node_id
            return (
              <li key={`${id}-${i}`} className="flex gap-3 text-sm">
                <span
                  className={cn(
                    'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
                    current
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted text-muted-foreground',
                  )}
                >
                  {i + 1}
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      'block',
                      current ? 'font-semibold text-foreground' : 'text-foreground',
                    )}
                  >
                    {node?.title ?? 'Step'}
                  </span>
                  {answer && (
                    <span className="block text-muted-foreground">→ {answer.answer_label}</span>
                  )}
                </span>
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}

function HistoryTimeline({ session }: { session: TroubleshootingSession }) {
  const nodeTitle = (id: string | null) =>
    session.guide.nodes.find((n) => n.id === id)?.title ?? 'step'
  if (session.steps.length === 0) {
    return <p className="text-sm text-muted-foreground">Nothing recorded yet.</p>
  }
  return (
    <ol className="relative flex flex-col gap-3 border-l pl-5">
      {session.steps.map((s) => (
        <li
          key={s.id}
          className={cn('relative text-sm', s.superseded && 'text-muted-foreground line-through')}
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
          {s.step_type === 'complete' && <span className="font-medium">Session completed</span>}
          {s.observation && (
            <span className="block text-xs text-muted-foreground">“{s.observation}”</span>
          )}
          {s.action_taken && (
            <span className="block text-xs text-muted-foreground">Action: {s.action_taken}</span>
          )}
        </li>
      ))}
    </ol>
  )
}

function SessionBadge({ status }: { status: TroubleshootingSession['status'] }) {
  const styles = {
    in_progress: ['In progress', 'border-blue-200 bg-blue-50 text-blue-800'],
    resolved: ['Resolved', 'border-emerald-200 bg-emerald-50 text-emerald-800'],
    unresolved: ['Not resolved', 'border-red-200 bg-red-50 text-red-800'],
  }[status]
  return (
    <span
      className={cn(
        'rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        styles[1],
      )}
    >
      {styles[0]}
    </span>
  )
}
