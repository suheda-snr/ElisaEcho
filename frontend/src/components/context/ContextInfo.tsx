import { CalendarClock, Cpu, History, KeyRound, MapPin, Network, Zap } from 'lucide-react'
import { Link } from 'react-router'

import { formatTime } from '@/components/discovery/labels'
import { cn } from '@/lib/utils'
import type { ContextFields, EntityLink, KnowledgeType } from '@/types/api'

function isOutdated(validTo: string | null | undefined): boolean {
  return Boolean(validTo) && new Date(validTo as string).getTime() <= Date.now()
}

export function KnowledgeTypeBadge({ type }: { type: KnowledgeType }) {
  if (type !== 'site_access') return null
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-800">
      <KeyRound className="size-3" aria-hidden="true" />
      Site access
    </span>
  )
}

export function OutdatedBadge({ validTo }: { validTo: string | null | undefined }) {
  if (!isOutdated(validTo)) return null
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-medium text-red-800">
      <History className="size-3" aria-hidden="true" />
      Outdated
    </span>
  )
}

const ENTITY_ICONS = { equipment: Cpu, unit_class: Network, site: MapPin, event: Zap }
const RELATION_LABELS: Record<EntityLink['relation'], string> = {
  observed_on: 'Observed on',
  applies_to: 'Applies to unit class',
  located_at: 'Site',
  access_to: 'Access to site',
  triggered_by: 'Event',
}

/** Validity period and the network entities the knowledge is bound to. */
export function ContextSection({ context }: { context: ContextFields }) {
  const outdated = isOutdated(context.valid_to)
  return (
    <section className="flex flex-col gap-3" aria-labelledby="context-title">
      <h3
        id="context-title"
        className="text-xs font-semibold tracking-wide text-muted-foreground uppercase"
      >
        Context and validity
      </h3>
      <div
        className={cn(
          'flex items-start gap-2 rounded-lg border px-3 py-2 text-sm',
          outdated ? 'border-red-200 bg-red-50 text-red-900' : 'bg-muted/30 text-foreground',
        )}
      >
        <CalendarClock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div className="flex flex-col gap-0.5">
          <span>
            Valid from {context.valid_from ? formatTime(context.valid_from) : 'unknown'}
            {outdated
              ? ` until ${formatTime(context.valid_to)}`
              : ' · still believed true (no newer information replaces it)'}
          </span>
          {outdated && context.superseded_by && (
            <span>
              Replaced by{' '}
              <Link
                to={`/knowledge?item=${context.superseded_by.id}`}
                className="font-medium underline"
              >
                {context.superseded_by.title}
              </Link>
              . Do not use this information for new work.
            </span>
          )}
          {context.validity_note && (
            <span className="text-xs opacity-80">{context.validity_note}</span>
          )}
        </div>
      </div>
      {context.entity_links.length > 0 ? (
        <ul className="flex flex-wrap gap-1.5" aria-label="Linked network entities">
          {context.entity_links.map((link) => {
            const Icon = ENTITY_ICONS[link.entity_type]
            return (
              <li
                key={`${link.entity_type}-${link.relation}-${link.label}`}
                className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-xs"
                title={
                  link.source === 'inventory'
                    ? 'Derived from the network inventory'
                    : 'Stated in the conversation'
                }
              >
                <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
                <span className="text-muted-foreground">{RELATION_LABELS[link.relation]}:</span>
                <span className="font-medium text-foreground">{link.label}</span>
                {link.source === 'inventory' && (
                  <span className="text-muted-foreground">(inventory)</span>
                )}
              </li>
            )
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Not linked to any known network entity.</p>
      )}
    </section>
  )
}
