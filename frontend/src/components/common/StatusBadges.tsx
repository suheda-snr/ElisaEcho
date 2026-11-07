import {
  BadgeCheck,
  CircleCheck,
  CircleDashed,
  CircleHelp,
  Cpu,
  Hash,
  Mail,
  MapPin,
  MessagesSquare,
  Network,
  Radio,
  XCircle,
  Zap,
} from 'lucide-react'

import { cn } from '@/lib/utils'
import type { ApprovalStatus, EntityLink, ResolutionStatus } from '@/types/api'

const pill =
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap'

/** Was the fix confirmed in the original conversation? */
export function ResolutionBadge({ status }: { status: ResolutionStatus }) {
  if (status === 'confirmed_in_conversation') {
    return (
      <span className={cn(pill, 'border-emerald-200 bg-emerald-50 text-emerald-800')}>
        <CircleCheck className="size-3" aria-hidden="true" />
        Confirmed in chat
      </span>
    )
  }
  if (status === 'suggested') {
    return (
      <span className={cn(pill, 'border-amber-200 bg-amber-50 text-amber-900')}>
        <CircleDashed className="size-3" aria-hidden="true" />
        Suggested
      </span>
    )
  }
  return (
    <span className={cn(pill, 'bg-muted text-muted-foreground')}>
      <CircleHelp className="size-3" aria-hidden="true" />
      Unclear
    </span>
  )
}

/** Expert review (separate from confirmation in chat). */
export function ReviewBadge({ status }: { status: ApprovalStatus }) {
  if (status === 'approved') {
    return (
      <span className={cn(pill, 'border-blue-200 bg-blue-50 text-blue-800')}>
        <BadgeCheck className="size-3" aria-hidden="true" />
        Expert-approved
      </span>
    )
  }
  if (status === 'rejected') {
    return (
      <span className={cn(pill, 'border-red-200 bg-red-50 text-red-800')}>
        <XCircle className="size-3" aria-hidden="true" />
        Rejected
      </span>
    )
  }
  return <span className={cn(pill, 'bg-background text-muted-foreground')}>Needs review</span>
}

const SOURCES: Record<string, { label: string; icon: typeof Hash }> = {
  slack: { label: 'Slack', icon: Hash },
  teams: { label: 'Teams', icon: MessagesSquare },
  email: { label: 'Email', icon: Mail },
  simulated: { label: 'Simulation', icon: Radio },
}

export function SourceBadge({
  type,
  className,
}: {
  type: string | null | undefined
  className?: string
}) {
  const source = SOURCES[type ?? ''] ?? { label: type ?? 'Unknown', icon: Radio }
  const Icon = source.icon
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs text-muted-foreground', className)}>
      <Icon className="size-3.5" aria-hidden="true" />
      {source.label}
    </span>
  )
}

const ENTITY_ICONS = { equipment: Cpu, unit_class: Network, site: MapPin, event: Zap }

/** Compact chips for the network entities a knowledge item is bound to. */
export function EntityChips({ links, max = 4 }: { links: EntityLink[]; max?: number }) {
  if (links.length === 0) return null
  // Most specific first: node, site, unit class, event.
  const order = { equipment: 0, site: 1, unit_class: 2, event: 3 }
  const sorted = [...links].sort((a, b) => order[a.entity_type] - order[b.entity_type])
  const unique = sorted.filter((l, i) => sorted.findIndex((o) => o.label === l.label) === i)
  const shown = unique.slice(0, max)
  return (
    <span className="flex flex-wrap items-center gap-1">
      {shown.map((link) => {
        const Icon = ENTITY_ICONS[link.entity_type]
        return (
          <span
            key={`${link.entity_type}-${link.label}`}
            className="inline-flex max-w-[16rem] items-center gap-1 rounded-md bg-accent px-1.5 py-0.5 text-xs font-medium text-accent-foreground"
            title={`${link.entity_type.replace('_', ' ')}: ${link.label}`}
          >
            <Icon className="size-3 shrink-0" aria-hidden="true" />
            <span className="truncate">{link.label}</span>
          </span>
        )
      })}
      {unique.length > shown.length && (
        <span className="text-xs text-muted-foreground">+{unique.length - shown.length}</span>
      )}
    </span>
  )
}
