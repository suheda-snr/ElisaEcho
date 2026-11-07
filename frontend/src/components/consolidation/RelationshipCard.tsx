import { ArrowRight, MessageSquareQuote, TriangleAlert } from 'lucide-react'
import { Link } from 'react-router'

import { formatTime } from '@/components/discovery/labels'
import { cn } from '@/lib/utils'
import type { CaseRef, KnowledgeRelationship, RelationshipEvidence } from '@/types/api'

import { relationshipInfo, toneClasses } from './labels'

export function RelationshipBadge({ type }: { type: KnowledgeRelationship['relationship_type'] }) {
  const info = relationshipInfo[type]
  return (
    <span
      title={info.hint}
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        toneClasses[info.tone],
      )}
    >
      {info.tone === 'conflict' && <TriangleAlert className="size-3" aria-hidden="true" />}
      {info.label}
    </span>
  )
}

function Unknown() {
  return <span className="text-muted-foreground italic">not stated</span>
}

function shortTitle(c: CaseRef) {
  return c.conversation ?? c.title
}

/**
 * One AI-assessed relationship. With `perspective` (a knowledge id) it reads "this case vs
 * the other case"; otherwise it shows the pair as stored.
 */
export function RelationshipCard({
  relationship: r,
  perspective,
}: {
  relationship: KnowledgeRelationship
  perspective?: string
}) {
  const flipped = perspective !== undefined && r.target.id === perspective
  const left = flipped ? r.target : r.source
  const right = flipped ? r.source : r.target
  const leftEvidence = flipped ? r.target_evidence : r.source_evidence
  const rightEvidence = flipped ? r.source_evidence : r.target_evidence
  const info = relationshipInfo[r.relationship_type]
  const leftLabel = perspective ? 'This case' : shortTitle(left)

  return (
    <article
      className={cn(
        'flex flex-col gap-3 rounded-lg border bg-background p-3',
        info.tone === 'conflict' && 'border-amber-300',
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <RelationshipBadge type={r.relationship_type} />
        {perspective ? (
          <Link
            to={`/knowledge?item=${right.id}`}
            className="inline-flex items-center gap-1 text-sm font-medium text-foreground hover:underline"
          >
            {right.title}
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        ) : (
          <span className="text-sm text-foreground">
            <Link to={`/knowledge?item=${left.id}`} className="font-medium hover:underline">
              {shortTitle(left)}
            </Link>
            <span className="text-muted-foreground"> ↔ </span>
            <Link to={`/knowledge?item=${right.id}`} className="font-medium hover:underline">
              {shortTitle(right)}
            </Link>
          </span>
        )}
      </div>
      {perspective && right.conversation && (
        <p className="-mt-2 text-xs text-muted-foreground">
          From “{right.conversation}”{right.source_name && ` · ${right.source_name}`}
        </p>
      )}
      {r.explanation && <p className="text-sm text-foreground">{r.explanation}</p>}

      {r.conditions.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Condition differences</caption>
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-1 pr-3 font-medium">Condition</th>
                <th className="py-1 pr-3 font-medium">{leftLabel}</th>
                <th className="py-1 font-medium">
                  {perspective ? 'Other case' : shortTitle(right)}
                </th>
              </tr>
            </thead>
            <tbody>
              {r.conditions.map((c) => {
                const a = flipped ? c.target_value : c.source_value
                const b = flipped ? c.source_value : c.target_value
                return (
                  <tr key={c.field} className="border-t">
                    <td className="py-1 pr-3 capitalize">{c.field}</td>
                    <td className="py-1 pr-3 font-mono">{a ?? <Unknown />}</td>
                    <td className="py-1 font-mono">{b ?? <Unknown />}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {r.unknown_conditions.length > 0 && (
        <p className="text-xs text-amber-900">
          Unknown, so not assumed to match: {r.unknown_conditions.join(', ')}
        </p>
      )}
      {(r.shared_equipment.length > 0 || r.shared_symptoms.length > 0) && (
        <p className="text-xs text-muted-foreground">
          {r.shared_symptoms.length > 0 && <>Shared symptoms: {r.shared_symptoms.join(', ')}. </>}
          {r.shared_equipment.length > 0 && <>Shared equipment: {r.shared_equipment.join(', ')}.</>}
        </p>
      )}

      {(leftEvidence.length > 0 || rightEvidence.length > 0) && (
        <details className="group text-sm">
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
            Evidence ({leftEvidence.length + rightEvidence.length} messages)
          </summary>
          <div className="mt-2 grid gap-3 md:grid-cols-2">
            <EvidenceList label={leftLabel} items={leftEvidence} />
            <EvidenceList
              label={perspective ? 'Other case' : shortTitle(right)}
              items={rightEvidence}
            />
          </div>
        </details>
      )}
      {r.validation_notes.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Server checks: {r.validation_notes.join(' ')}
        </p>
      )}
    </article>
  )
}

function EvidenceList({ label, items }: { label: string; items: RelationshipEvidence[] }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-semibold text-muted-foreground">{label}</span>
      {items.length === 0 && (
        <span className="text-xs text-muted-foreground">No message cited.</span>
      )}
      {items.map((e) => (
        <blockquote
          key={e.message_id}
          className="flex gap-2 rounded-md border-l-2 border-primary/40 bg-muted/40 px-2 py-1.5"
        >
          <MessageSquareQuote
            className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
            aria-hidden="true"
          />
          <span className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground">
              {e.author} · {formatTime(e.sent_at)}
            </span>
            <span className="text-sm whitespace-pre-wrap text-foreground">{e.excerpt}</span>
          </span>
        </blockquote>
      ))}
    </div>
  )
}
