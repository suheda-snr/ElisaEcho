import { Network } from 'lucide-react'
import { Link } from 'react-router'

import { Button } from '@/components/ui/button'
import { useRelatedKnowledge } from '@/hooks/useConsolidation'
import { getErrorMessage } from '@/services/api'

import { groupHeadline, relationshipInfo } from './labels'
import { RelationshipCard } from './RelationshipCard'

/** Related knowledge for one item: its group (if any) and AI-assessed relationships. */
export function RelatedKnowledgeSection({ itemId }: { itemId: string }) {
  const related = useRelatedKnowledge(itemId)
  const data = related.data
  const strong =
    data?.relationships.filter((r) => relationshipInfo[r.relationship_type].tone !== 'weak') ?? []
  const weak =
    data?.relationships.filter((r) => relationshipInfo[r.relationship_type].tone === 'weak') ?? []

  return (
    <section className="flex flex-col gap-3" aria-labelledby="related-knowledge">
      <h3
        id="related-knowledge"
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        Related knowledge
      </h3>
      {related.isError && <p className="text-sm text-red-700">{getErrorMessage(related.error)}</p>}
      {data?.group && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2">
          <div className="flex flex-col">
            <span className="text-sm font-medium text-foreground">{data.group.title}</span>
            <span className="text-xs text-muted-foreground">
              {groupHeadline(data.group)} · {data.group.independent_conversations} independent
              conversations
              {data.group.conflict_count > 0 &&
                ` · ${data.group.conflict_count} conflicting report(s)`}
            </span>
          </div>
          <Button size="sm" variant="outline" asChild>
            <Link to={`/knowledge?group=${data.group.id}`}>
              <Network aria-hidden="true" />
              Compare related cases
            </Link>
          </Button>
        </div>
      )}
      {data && data.relationships.length === 0 && (
        <p className="rounded-lg border border-dashed px-3 py-3 text-sm text-muted-foreground">
          No related knowledge found yet. New knowledge is compared automatically with similar cases
          after it is discovered.
        </p>
      )}
      {strong.map((r) => (
        <RelationshipCard key={r.id} relationship={r} perspective={itemId} />
      ))}
      {weak.length > 0 && (
        <details>
          <summary className="cursor-pointer text-xs font-medium text-muted-foreground hover:text-foreground">
            {weak.length} case(s) with similar symptoms only (suggestions, not grouped)
          </summary>
          <div className="mt-2 flex flex-col gap-3">
            {weak.map((r) => (
              <RelationshipCard key={r.id} relationship={r} perspective={itemId} />
            ))}
          </div>
        </details>
      )}
      {data && data.relationships.length > 0 && (
        <p className="text-xs text-muted-foreground">
          AI-assessed and checked against the cited messages.
        </p>
      )}
    </section>
  )
}
