import { CircleAlert, ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { evidenceLabels, formatTime, resolutionLabels } from '@/components/discovery/labels'
import { nodeTypeStyle, supportStyle } from '@/components/troubleshooting/nodeStyles'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Guide, GuideNode } from '@/types/api'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {title}
      </h3>
      {children}
    </section>
  )
}

export function EvidencePanel({ guide, node }: { guide: Guide; node: GuideNode | null }) {
  if (!node) {
    return (
      <p className="text-sm text-muted-foreground">
        Select a step in the tree to see its evidence.
      </p>
    )
  }
  const style = nodeTypeStyle[node.node_type]
  const support = supportStyle[node.support_level]
  const knowledge = guide.knowledge.filter((k) => node.knowledge_item_ids.includes(k.id))
  const Icon = style.icon

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <span
          className={cn(
            'inline-flex w-fit items-center gap-1 rounded px-2 py-0.5 text-xs font-medium',
            style.chip,
          )}
        >
          <Icon className="size-3.5" aria-hidden="true" />
          {style.label}
        </span>
        <h3 className="text-base font-semibold text-foreground">{node.title}</h3>
        <div className="flex flex-wrap gap-1.5">
          {support && (
            <span
              className={cn(
                'rounded-full border px-2.5 py-0.5 text-xs font-medium',
                support.className,
              )}
            >
              {support.label}
            </span>
          )}
          {node.approval_status && (
            <Badge variant="outline">
              {node.approval_status === 'approved'
                ? 'Expert-approved'
                : `Approval: ${node.approval_status}`}
            </Badge>
          )}
        </div>
      </div>

      {node.requires_manual_verification && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <ShieldAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>Not an approved procedure: check it applies and follow your change process.</span>
        </div>
      )}

      {node.conflict_note && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            <span className="font-medium">Conflicting evidence: </span>
            {node.conflict_note}
          </span>
        </div>
      )}

      {(node.description || node.question) && (
        <Section title="Details">
          {node.question && <p className="text-sm font-medium text-foreground">{node.question}</p>}
          {node.description && <p className="text-sm text-muted-foreground">{node.description}</p>}
        </Section>
      )}

      {node.applicability_conditions.length > 0 && (
        <Section title="Applies when">
          <ul className="list-disc pl-5 text-sm text-foreground">
            {node.applicability_conditions.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Source messages">
        {node.evidence.length === 0 ? (
          <p className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
            {node.node_type === 'start' ||
            node.node_type === 'question' ||
            node.node_type === 'escalation'
              ? 'Navigation step; it does not make a technical claim.'
              : 'No supporting messages.'}
          </p>
        ) : (
          <ol className="flex flex-col gap-3">
            {node.evidence.map((e) => (
              <li key={e.message_id}>
                <div className="mb-1 flex flex-wrap items-baseline gap-x-2 text-xs">
                  <span className="font-medium text-foreground">{e.author}</span>
                  <span className="text-muted-foreground">{formatTime(e.sent_at)}</span>
                  <Badge variant="outline">{evidenceLabels[e.evidence_type]}</Badge>
                </div>
                <blockquote className="rounded-lg border-l-2 border-primary/40 bg-muted/40 px-3 py-2 text-sm whitespace-pre-wrap text-foreground">
                  {e.deleted_at_source ? (
                    <span className="text-muted-foreground italic">
                      Message deleted at the source.
                    </span>
                  ) : (
                    e.excerpt
                  )}
                </blockquote>
                <p className="mt-1 text-xs text-muted-foreground">
                  {e.source_name ?? 'Unknown source'}
                  {e.source_type && ` (${e.source_type})`}
                  {e.thread_title && ` · ${e.thread_title}`}
                </p>
              </li>
            ))}
          </ol>
        )}
      </Section>

      {knowledge.length > 0 && (
        <Section title="Knowledge behind this step">
          <ul className="flex flex-col gap-2">
            {knowledge.map((k) => (
              <li key={k.id} className="rounded-lg border bg-background p-3 text-sm">
                <Link
                  to={`/knowledge?item=${k.id}`}
                  className="font-medium text-foreground hover:underline"
                >
                  {k.title}
                </Link>
                <p className="text-xs text-muted-foreground">
                  {k.conversation ?? 'Unknown conversation'}
                  {k.equipment_identifiers.length > 0 && ` · ${k.equipment_identifiers.join(', ')}`}
                </p>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  <Badge variant="secondary">{resolutionLabels[k.resolution_status]}</Badge>
                  <Badge variant="outline">
                    {k.approval_status === 'approved' ? 'Expert-approved' : 'Not expert-reviewed'}
                  </Badge>
                </div>
                {k.missing_information.length > 0 && (
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    Missing: {k.missing_information.join('; ')}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  )
}
