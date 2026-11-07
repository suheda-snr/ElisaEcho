import { Background, MarkerType, ReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { CircleDashed, Network, TriangleAlert, Workflow } from 'lucide-react'
import { type ReactNode, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'

import {
  groupHeadline,
  relationshipInfo,
  solutionOutcomeClasses,
  solutionOutcomeLabels,
} from '@/components/consolidation/labels'
import { RelationshipCard } from '@/components/consolidation/RelationshipCard'
import { KnowledgeTypeBadge, OutdatedBadge } from '@/components/context/ContextInfo'
import { Disclosure } from '@/components/common/Disclosure'
import { EmptyState, Notice } from '@/components/common/States'
import { ResolutionBadge } from '@/components/common/StatusBadges'
import { InventoryCard } from '@/components/sources/InventoryCard'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  useGroupRelationships,
  useKnowledgeGroup,
  useKnowledgeGroups,
} from '@/hooks/useConsolidation'
import { cn } from '@/lib/utils'
import { getErrorMessage } from '@/services/api'
import type { GroupDetail, KnowledgeRelationship } from '@/types/api'

export default function KnowledgeNetwork() {
  const [params, setParams] = useSearchParams()
  const groups = useKnowledgeGroups()
  const items = groups.data?.items ?? []
  const selectedId = params.get('group') ?? items[0]?.id ?? null
  const detail = useKnowledgeGroup(selectedId)
  const relationships = useGroupRelationships(selectedId)

  return (
    <div className="flex flex-col gap-5">
      <p className="text-[15px] text-muted-foreground">
        Related cases from separate conversations, grouped automatically: which fix worked under
        which conditions, and where reports disagree.
      </p>

      {groups.isError && <Notice tone="error">{getErrorMessage(groups.error)}</Notice>}

      {groups.data && items.length === 0 ? (
        <EmptyState
          icon={CircleDashed}
          title="No related cases yet"
          action={
            <Button asChild>
              <Link to="/discovery">Open Live Discovery</Link>
            </Button>
          }
        >
          When new knowledge matches earlier cases (same problem, supporting evidence or a different
          outcome), they are grouped here.
        </EmptyState>
      ) : (
        <div className="grid gap-6 lg:grid-cols-12">
          <ul className="flex flex-col gap-2 lg:col-span-4" aria-label="Knowledge groups">
            {items.map((g) => (
              <li key={g.id}>
                <button
                  type="button"
                  onClick={() => setParams({ group: g.id }, { replace: true })}
                  aria-pressed={g.id === selectedId}
                  className={cn(
                    'flex w-full flex-col gap-1.5 rounded-xl border bg-card p-3 text-left transition-colors',
                    'focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                    g.id === selectedId
                      ? 'border-primary/50 ring-1 ring-primary/30'
                      : 'hover:bg-muted/40',
                  )}
                >
                  <span className="text-sm font-medium text-foreground">{g.title}</span>
                  <span className="text-xs text-muted-foreground">{groupHeadline(g)}</span>
                  <span className="flex flex-wrap gap-1.5">
                    <Badge variant="outline">{g.independent_conversations} conversations</Badge>
                    {g.conflict_count > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-900">
                        <TriangleAlert className="size-3" aria-hidden="true" />
                        {g.conflict_count} conflicting
                      </span>
                    )}
                    {g.summary_pending && <Badge variant="secondary">Summary updating</Badge>}
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <div className="lg:col-span-8">
            {detail.isError && (
              <p className="text-sm text-red-700">{getErrorMessage(detail.error)}</p>
            )}
            {detail.data ? (
              <GroupView group={detail.data} relationships={relationships.data ?? []} />
            ) : (
              selectedId && <p className="text-sm text-muted-foreground">Loading…</p>
            )}
          </div>
        </div>
      )}

      <Disclosure title="Network inventory (nodes, unit classes, sites)">
        <InventoryCard />
      </Disclosure>
    </div>
  )
}

function Section({
  title,
  icon,
  children,
}: {
  title: string
  icon?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  )
}

function List({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <ul className="list-disc pl-5 text-sm text-foreground">
      {items.map((i) => (
        <li key={i}>{i}</li>
      ))}
    </ul>
  )
}

function GroupView({
  group,
  relationships,
}: {
  group: GroupDetail
  relationships: KnowledgeRelationship[]
}) {
  const caseLabel = useMemo(
    () => new Map(group.members.map((m, i) => [m.id, `Case ${i + 1}`])),
    [group.members],
  )
  const withConditions = relationships.filter(
    (r) => r.conditions.length > 0 || r.unknown_conditions.length > 0,
  )
  const problem = group.shared_problem ?? group.members[0]?.problem_description ?? group.title

  return (
    <Card>
      <CardContent className="flex flex-col gap-6">
        <div className="flex flex-col gap-3">
          <h2 className="text-xl font-semibold text-foreground">{group.title}</h2>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="outline">{groupHeadline(group)}</Badge>
            <Badge variant="outline">
              {group.independent_conversations} independent conversations
            </Badge>
            <Badge variant="secondary">AI summary · needs review</Badge>
          </div>
          <div>
            <Button size="sm" asChild>
              <Link to={`/troubleshoot?problem=${encodeURIComponent(problem)}`}>
                <Workflow aria-hidden="true" />
                Troubleshoot with these cases
              </Link>
            </Button>
          </div>
        </div>

        {group.summary_pending && (
          <Notice tone="info">The summary is being updated for recent changes.</Notice>
        )}

        <div className="grid gap-6 md:grid-cols-2">
          <Section title="Shared problem">
            <p className="text-sm text-foreground">{problem}</p>
            {group.shared_symptoms.length > 0 && <List items={group.shared_symptoms} empty="" />}
          </Section>
          <Section title="Known environment">
            <List items={group.known_environment} empty="Not stated in the conversations." />
          </Section>
        </div>

        <Section title="Compare cases">
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Case</th>
                  <th className="px-3 py-2 font-medium">Reported fix</th>
                  <th className="px-3 py-2 font-medium">Where</th>
                  <th className="px-3 py-2 font-medium">Conditions</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {group.members.map((m) => (
                  <tr key={m.id} className="border-t align-top">
                    <td className="px-3 py-2.5">
                      <Link
                        to={`/knowledge?item=${m.id}`}
                        className="font-medium text-foreground hover:underline"
                      >
                        {caseLabel.get(m.id)}
                      </Link>
                      <span
                        className="block max-w-48 truncate text-xs text-muted-foreground"
                        title={m.conversation ?? m.title}
                      >
                        {m.conversation ?? m.title}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-foreground">{m.resolution ?? '–'}</td>
                    <td className="px-3 py-2.5 font-mono text-xs whitespace-nowrap">
                      {m.equipment.join(', ') || (
                        <span className="font-sans text-muted-foreground">not stated</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-foreground/80">
                      {m.applicability_conditions.slice(0, 2).join('; ') || (
                        <span className="text-muted-foreground">not stated</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="flex flex-col items-start gap-1">
                        <ResolutionBadge status={m.resolution_status} />
                        <OutdatedBadge validTo={m.valid_to} />
                        <KnowledgeTypeBadge type={m.knowledge_type} />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title={`Resolution paths (${group.solutions.length})`}>
          {group.solutions.length === 0 && (
            <p className="text-sm text-muted-foreground">No resolution paths summarized yet.</p>
          )}
          <ol className="flex flex-col gap-2">
            {group.solutions.map((s) => (
              <li
                key={s.description}
                className="flex flex-col gap-2 rounded-lg border bg-background p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-medium text-foreground">{s.description}</span>
                  <span
                    className={cn(
                      'rounded-full border px-2 py-0.5 text-xs font-medium',
                      solutionOutcomeClasses[s.outcome],
                    )}
                  >
                    {solutionOutcomeLabels[s.outcome]}
                  </span>
                </div>
                {s.conditions.length > 0 && (
                  <ul className="list-disc pl-5 text-sm text-muted-foreground">
                    {s.conditions.map((c) => (
                      <li key={c}>{c}</li>
                    ))}
                  </ul>
                )}
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                  Reported in
                  {s.knowledge_ids.map((id) => (
                    <Link
                      key={id}
                      to={`/knowledge?item=${id}`}
                      className="rounded border bg-muted px-1.5 font-medium text-foreground hover:underline"
                    >
                      {caseLabel.get(id) ?? 'case'}
                    </Link>
                  ))}
                </div>
              </li>
            ))}
          </ol>
        </Section>

        <div className="grid gap-6 md:grid-cols-3">
          <Section title="Failed attempts">
            <List items={group.failed_attempts} empty="None reported." />
          </Section>
          <Section
            title="Contradictions"
            icon={
              group.contradictions.length > 0 ? (
                <TriangleAlert className="size-3.5 text-amber-700" aria-hidden="true" />
              ) : undefined
            }
          >
            <List items={group.contradictions} empty="None found." />
          </Section>
          <Section title="Missing information">
            <List items={group.missing_information} empty="Nothing flagged." />
          </Section>
        </div>

        <Disclosure title="Pairwise comparisons and evidence" count={relationships.length}>
          {relationships.length === 0 ? (
            <p className="text-sm text-muted-foreground">No pairwise comparisons available.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {[...withConditions, ...relationships.filter((r) => !withConditions.includes(r))].map(
                (r) => (
                  <RelationshipCard key={r.id} relationship={r} />
                ),
              )}
            </div>
          )}
        </Disclosure>

        <Disclosure title="Show relationship graph">
          <CaseGraph group={group} relationships={relationships} caseLabel={caseLabel} />
        </Disclosure>

        <p className="text-xs text-muted-foreground">
          Summary generated by {group.summary_model ?? 'AI'}
          {group.generated_at && ` on ${new Date(group.generated_at).toLocaleString()}`}. Values
          such as firmware versions are only shown when they appear in the original messages.
        </p>
      </CardContent>
    </Card>
  )
}

const EDGE_COLORS = {
  support: '#059669',
  conflict: '#d97706',
  conditions: '#0284c7',
  weak: '#94a3b8',
}

function CaseGraph({
  group,
  relationships,
  caseLabel,
}: {
  group: GroupDetail
  relationships: KnowledgeRelationship[]
  caseLabel: Map<string, string>
}) {
  const { nodes, edges } = useMemo(() => {
    const n = group.members.length
    const radius = n <= 2 ? 160 : 190
    const nodes: Node[] = group.members.map((m, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2
      return {
        id: m.id,
        position: {
          x: 260 + radius * Math.cos(angle) - 90,
          y: 150 + radius * 0.75 * Math.sin(angle) - 25,
        },
        data: { label: `${caseLabel.get(m.id)}: ${m.conversation ?? m.title}` },
        style: { width: 180, fontSize: 12 },
        draggable: false,
      }
    })
    const edges: Edge[] = relationships.map((r) => {
      const info = relationshipInfo[r.relationship_type]
      return {
        id: r.id,
        source: r.source.id,
        target: r.target.id,
        label: info.label,
        labelStyle: { fontSize: 11 },
        style: {
          stroke: EDGE_COLORS[info.tone],
          strokeWidth: 2,
          strokeDasharray: info.tone === 'conflict' ? '6 4' : undefined,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: EDGE_COLORS[info.tone] },
      }
    })
    return { nodes, edges }
  }, [group.members, relationships, caseLabel])

  return (
    <figure className="flex flex-col gap-2">
      <div className="h-80 w-full overflow-hidden rounded-lg border bg-background">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesConnectable={false}
          nodesDraggable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
        </ReactFlow>
      </div>
      <figcaption className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        <Network className="size-3.5" aria-hidden="true" />
        <Legend color={EDGE_COLORS.support} label="Supports / same problem" />
        <Legend color={EDGE_COLORS.conditions} label="Different conditions" />
        <Legend color={EDGE_COLORS.conflict} label="Different outcome / conflict" dashed />
      </figcaption>
    </figure>
  )
}

function Legend({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width="20" height="6" aria-hidden="true">
        <line
          x1="0"
          y1="3"
          x2="20"
          y2="3"
          stroke={color}
          strokeWidth="2"
          strokeDasharray={dashed ? '4 3' : undefined}
        />
      </svg>
      {label}
    </span>
  )
}
