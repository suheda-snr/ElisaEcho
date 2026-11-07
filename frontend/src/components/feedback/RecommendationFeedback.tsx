import { CircleCheck, MessageSquareHeart, Pencil, ShieldCheck } from 'lucide-react'
import { type FormEvent, useMemo, useState } from 'react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { feedbackToken, useSaveFeedback, useSessionFeedback } from '@/hooks/useFeedback'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type {
  FeedbackInput,
  GuideNode,
  TroubleshootingFeedback,
  TroubleshootingSession,
} from '@/types/api'

import { outcomeClasses, outcomeHints, outcomeLabels } from './labels'

type AttemptOutcome = Exclude<FeedbackInput['outcome'], undefined>
const OUTCOMES: AttemptOutcome[] = ['resolved', 'not_resolved', 'partially_resolved', 'unknown']

const inputClass =
  'h-9 w-full rounded-lg border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none'

/** Recommendation/resolution steps with sources that the engineer actually reached. */
function reachedRecommendations(session: TroubleshootingSession): GuideNode[] {
  const reached = new Set<string>()
  if (session.current_node_id) reached.add(session.current_node_id)
  for (const s of session.steps) {
    if (s.node_id) reached.add(s.node_id)
    if (s.target_node_id) reached.add(s.target_node_id)
  }
  return session.guide.nodes.filter(
    (n) =>
      (n.node_type === 'recommendation' || n.node_type === 'resolution') &&
      n.knowledge_item_ids.length > 0 &&
      reached.has(n.id),
  )
}

export function RecommendationFeedback({ session }: { session: TroubleshootingSession }) {
  const nodes = useMemo(() => reachedRecommendations(session), [session])
  const feedback = useSessionFeedback(session.id)
  const [chosen, setChosen] = useState<string | null>(null)
  const current = nodes.find((n) => n.id === session.current_node_id)
  const node = nodes.find((n) => n.id === chosen) ?? current ?? nodes[nodes.length - 1] ?? null

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquareHeart className="size-4" aria-hidden="true" />
          Did it work?
        </CardTitle>
        <CardDescription>
          Report the result of a recommendation. Your report becomes new evidence on the original
          knowledge for the next engineer.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {nodes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Follow the guide to a recommendation, then report here whether you tried it and what
            happened.
          </p>
        ) : (
          <>
            {nodes.length > 1 && (
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Recommendation">
                {nodes.map((n) => {
                  const done = feedback.data?.some((f) => f.guide_node_id === n.id)
                  return (
                    <button
                      key={n.id}
                      type="button"
                      onClick={() => setChosen(n.id)}
                      aria-pressed={n.id === node?.id}
                      className={cn(
                        'rounded-full border px-2.5 py-1 text-xs transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                        n.id === node?.id
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'bg-card hover:bg-muted',
                      )}
                    >
                      {done && '✓ '}
                      {n.title}
                    </button>
                  )
                })}
              </div>
            )}
            {node && (
              <NodeFeedback
                key={node.id}
                session={session}
                node={node}
                existing={feedback.data ?? []}
              />
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

function NodeFeedback({
  session,
  node,
  existing,
}: {
  session: TroubleshootingSession
  node: GuideNode
  existing: TroubleshootingFeedback[]
}) {
  const sources = session.guide.knowledge.filter((k) => node.knowledge_item_ids.includes(k.id))
  const [knowledgeId, setKnowledgeId] = useState(sources[0]?.id ?? node.knowledge_item_ids[0])
  const saved = existing.find(
    (f) => f.guide_node_id === node.id && f.knowledge_item_id === knowledgeId,
  )
  const [editing, setEditing] = useState(false)

  if (saved && !editing) {
    return <SavedFeedback feedback={saved} onEdit={() => setEditing(true)} />
  }
  // Prefill conditions from the guide, or from the engineer's earlier report in this session.
  const previous = existing[existing.length - 1]
  const source = sources.find((k) => k.id === knowledgeId)
  return (
    <FeedbackForm
      key={`${knowledgeId}-${saved?.revision ?? 0}`}
      session={session}
      node={node}
      knowledgeId={knowledgeId}
      sources={sources}
      onKnowledge={setKnowledgeId}
      saved={saved}
      initial={{
        equipment:
          saved?.equipment_identifier ??
          previous?.equipment_identifier ??
          session.guide.equipment_identifier ??
          (source?.equipment_identifiers.length === 1 ? source.equipment_identifiers[0] : ''),
        firmware: saved?.firmware_version ?? previous?.firmware_version ?? '',
        environment:
          saved?.environment_details?.details ?? previous?.environment_details?.details ?? '',
        notes: saved?.engineer_notes ?? '',
        attempted: saved ? saved.attempted : null,
        outcome: saved && saved.outcome !== 'not_attempted' ? saved.outcome : null,
      }}
      onDone={() => setEditing(false)}
    />
  )
}

function SavedFeedback({
  feedback: f,
  onEdit,
}: {
  feedback: TroubleshootingFeedback
  onEdit: () => void
}) {
  const canEdit = feedbackToken(f.id) !== null
  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-muted/30 p-3 text-sm">
      <p className="flex items-center gap-1.5 font-medium text-foreground">
        <CircleCheck className="size-4 text-emerald-700" aria-hidden="true" />
        Feedback saved for “{f.recommendation}”
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          className={cn(
            'rounded-full border px-2 py-0.5 text-xs font-medium',
            outcomeClasses[f.outcome],
          )}
        >
          {outcomeLabels[f.outcome]}
        </span>
        <span className="text-xs text-muted-foreground">
          {[f.equipment_identifier, f.firmware_version && `firmware ${f.firmware_version}`]
            .filter(Boolean)
            .join(' · ') || 'No conditions given'}
        </span>
      </div>
      {f.engineer_notes && <p className="text-xs text-muted-foreground">“{f.engineer_notes}”</p>}
      <p className="text-xs text-muted-foreground">
        Self-reported · revision {f.revision} ·{' '}
        <Link
          to={`/knowledge?item=${f.knowledge_item_id}`}
          className="underline hover:text-foreground"
        >
          view on the knowledge item
        </Link>
      </p>
      {canEdit ? (
        <Button size="sm" variant="outline" className="w-fit" onClick={onEdit}>
          <Pencil aria-hidden="true" />
          Correct my feedback
        </Button>
      ) : (
        <p className="text-xs text-muted-foreground">
          Submitted from another browser; it can only be corrected there.
        </p>
      )}
    </div>
  )
}

interface Initial {
  equipment: string
  firmware: string
  environment: string
  notes: string
  attempted: boolean | null
  outcome: AttemptOutcome | null
}

function FeedbackForm({
  session,
  node,
  knowledgeId,
  sources,
  onKnowledge,
  saved,
  initial,
  onDone,
}: {
  session: TroubleshootingSession
  node: GuideNode
  knowledgeId: string
  sources: TroubleshootingSession['guide']['knowledge']
  onKnowledge: (id: string) => void
  saved: TroubleshootingFeedback | undefined
  initial: Initial
  onDone: () => void
}) {
  const { submit, correct } = useSaveFeedback()
  const [attempted, setAttempted] = useState<boolean | null>(initial.attempted)
  const [outcome, setOutcome] = useState<AttemptOutcome | null>(initial.outcome)
  const [equipment, setEquipment] = useState(initial.equipment)
  const [firmware, setFirmware] = useState(initial.firmware)
  const [environment, setEnvironment] = useState(initial.environment)
  const [notes, setNotes] = useState(initial.notes)
  const [done, setDone] = useState(false)
  const mutation = saved ? correct : submit
  const ready = attempted === false || (attempted === true && outcome !== null)

  const save = (event: FormEvent) => {
    event.preventDefault()
    if (!ready) return
    const body: FeedbackInput = {
      attempted: attempted === true,
      outcome: attempted ? (outcome ?? undefined) : undefined,
      equipment_identifier: equipment.trim() || undefined,
      firmware_version: firmware.trim() || undefined,
      environment_details: environment.trim() ? { details: environment.trim() } : undefined,
      engineer_notes: notes.trim() || undefined,
    }
    const onSuccess = () => {
      setDone(true)
      onDone()
    }
    if (saved) correct.mutate({ id: saved.id, body }, { onSuccess })
    else
      submit.mutate(
        {
          ...body,
          troubleshooting_session_id: session.id,
          guide_node_id: node.id,
          knowledge_item_id: knowledgeId,
        },
        { onSuccess },
      )
  }

  return (
    <form onSubmit={save} className="flex flex-col gap-3" aria-label={`Feedback on ${node.title}`}>
      <p className="text-sm">
        <span className="text-muted-foreground">Recommendation: </span>
        <span className="font-medium text-foreground">{node.title}</span>
      </p>
      {sources.length > 1 && (
        <label className="flex flex-col gap-1 text-xs text-muted-foreground">
          Which approach did you follow?
          <select
            value={knowledgeId}
            onChange={(e) => onKnowledge(e.target.value)}
            className={inputClass}
          >
            {sources.map((k) => (
              <option key={k.id} value={k.id}>
                {k.title}
              </option>
            ))}
          </select>
        </label>
      )}

      <fieldset className="flex flex-col gap-1.5">
        <legend className="mb-1 text-xs font-semibold text-muted-foreground">
          1. Did you try it?
        </legend>
        <div className="grid grid-cols-2 gap-2">
          <Choice selected={attempted === true} onClick={() => setAttempted(true)}>
            Yes, I tried it
          </Choice>
          <Choice
            selected={attempted === false}
            onClick={() => {
              setAttempted(false)
              setOutcome(null)
            }}
          >
            No, I did not
          </Choice>
        </div>
      </fieldset>

      {attempted && (
        <fieldset className="flex flex-col gap-1.5">
          <legend className="mb-1 text-xs font-semibold text-muted-foreground">
            2. What was the result?
          </legend>
          <div className="grid grid-cols-2 gap-2">
            {OUTCOMES.map((o) => (
              <Choice
                key={o}
                selected={outcome === o}
                onClick={() => setOutcome(o)}
                hint={outcomeHints[o]}
              >
                {outcomeLabels[o]}
              </Choice>
            ))}
          </div>
        </fieldset>
      )}

      <details className="group" open={Boolean(initial.firmware || initial.notes)}>
        <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
          Conditions and notes (optional)
        </summary>
        <div className="mt-2 grid gap-2">
          <input
            value={equipment}
            onChange={(e) => setEquipment(e.target.value)}
            maxLength={100}
            placeholder="Equipment, e.g. S42-RTR-01"
            aria-label="Equipment identifier"
            className={inputClass}
          />
          <input
            value={firmware}
            onChange={(e) => setFirmware(e.target.value)}
            maxLength={100}
            placeholder="Firmware or software version, e.g. 3.2"
            aria-label="Firmware or software version"
            className={inputClass}
          />
          <input
            value={environment}
            onChange={(e) => setEnvironment(e.target.value)}
            maxLength={300}
            placeholder="Environment or configuration details"
            aria-label="Environment or configuration details"
            className={inputClass}
          />
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            maxLength={2000}
            rows={2}
            placeholder="What did you observe?"
            aria-label="Observations and notes"
            className={cn(inputClass, 'h-auto py-2')}
          />
        </div>
      </details>

      <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
        <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        Saved as self-reported. It never changes the knowledge's approval.
      </p>
      <Button type="submit" size="sm" className="w-fit" disabled={!ready || mutation.isPending}>
        {saved ? 'Save correction' : 'Save feedback'}
      </Button>
      {mutation.error != null && (
        <p className="text-sm text-red-700">{getErrorMessage(mutation.error)}</p>
      )}
      {done && <p className="text-sm text-emerald-800">Saved.</p>}
    </form>
  )
}

function Choice({
  selected,
  onClick,
  hint,
  children,
}: {
  selected: boolean
  onClick: () => void
  hint?: string
  children: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      title={hint}
      className={cn(
        'rounded-lg border px-2.5 py-2 text-left text-sm transition-colors focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
        selected
          ? 'border-primary bg-primary/10 font-medium text-foreground'
          : 'bg-card hover:bg-muted',
      )}
    >
      {children}
      {hint && <span className="block text-xs font-normal text-muted-foreground">{hint}</span>}
    </button>
  )
}

/** Feedback for one step, shown right after the engineer performs it. */
export function StepFeedback({
  session,
  node,
}: {
  session: TroubleshootingSession
  node: GuideNode
}) {
  const feedback = useSessionFeedback(session.id)
  if (node.knowledge_item_ids.length === 0) return null
  return <NodeFeedback key={node.id} session={session} node={node} existing={feedback.data ?? []} />
}
