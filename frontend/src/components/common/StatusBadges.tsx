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

/** Shared tag shape: compact, tinted, no outline. */
export const tagClass =
  'inline-flex h-[22px] items-center gap-1 rounded-md px-1.5 text-xs font-medium whitespace-nowrap'

/** Was the fix confirmed in the original conversation? */
export function ResolutionBadge({ status }: { status: ResolutionStatus }) {
  if (status === 'confirmed_in_conversation') {
    return (
      <span className={cn(tagClass, 'bg-emerald-50 text-emerald-800')}>
        <CircleCheck className="size-3.5" aria-hidden="true" />
        Confirmed in chat
      </span>
    )
  }
  if (status === 'suggested') {
    return (
      <span className={cn(tagClass, 'bg-amber-50 text-amber-900')}>
        <CircleDashed className="size-3.5" aria-hidden="true" />
        Suggested
      </span>
    )
  }
  return (
    <span className={cn(tagClass, 'bg-muted text-muted-foreground')}>
      <CircleHelp className="size-3.5" aria-hidden="true" />
      Unclear
    </span>
  )
}

/** Expert review (separate from confirmation in chat). */
export function ReviewBadge({ status }: { status: ApprovalStatus }) {
  if (status === 'approved') {
    return (
      <span className={cn(tagClass, 'bg-blue-50 text-blue-800')}>
        <BadgeCheck className="size-3.5" aria-hidden="true" />
        Expert-approved
      </span>
    )
  }
  if (status === 'rejected') {
    return (
      <span className={cn(tagClass, 'bg-red-50 text-red-800')}>
        <XCircle className="size-3.5" aria-hidden="true" />
        Rejected
      </span>
    )
  }
  return <span className={cn(tagClass, 'bg-muted text-muted-foreground')}>Needs review</span>
}

/** Each channel gets its own quiet accent so its origin reads at a glance, in lists and transcripts alike. */
const SOURCES: Record<string, { label: string; icon: typeof Hash; tone: string }> = {
  slack: { label: 'Slack', icon: Hash, tone: 'text-violet-500' },
  teams: { label: 'Teams', icon: MessagesSquare, tone: 'text-sky-600' },
  email: { label: 'Email', icon: Mail, tone: 'text-slate-500' },
  simulated: { label: 'Simulation', icon: Radio, tone: 'text-orange-500' },
}

export function SourceBadge({
  type,
  className,
}: {
  type: string | null | undefined
  className?: string
}) {
  const source = SOURCES[type ?? ''] ?? {
    label: type ?? 'Unknown',
    icon: Radio,
    tone: 'text-muted-foreground',
  }
  const Icon = source.icon
  return (
    <span
      className={cn('inline-flex items-center gap-1.5 text-xs text-muted-foreground', className)}
    >
      <Icon className={cn('size-3.5', source.tone)} aria-hidden="true" />
      {source.label}
    </span>
  )
}

const ENTITY_ICONS = { equipment: Cpu, unit_class: Network, site: MapPin, event: Zap }

/** Network entities a knowledge item is bound to. Node and site IDs are set in mono. */
export function EntityChips({ links, max = 4 }: { links: EntityLink[]; max?: number }) {
  if (links.length === 0) return null
  // Most specific first: node, site, unit class, event.
  const order = { equipment: 0, site: 1, unit_class: 2, event: 3 }
  const sorted = [...links].sort((a, b) => order[a.entity_type] - order[b.entity_type])
  const unique = sorted.filter((l, i) => sorted.findIndex((o) => o.label === l.label) === i)
  const shown = unique.slice(0, max)
  const hidden = unique.slice(max)
  return (
    <span className="flex flex-wrap items-center gap-1">
      {shown.map((link) => {
        const Icon = ENTITY_ICONS[link.entity_type]
        const isId = link.entity_type === 'equipment' || link.entity_type === 'site'
        return (
          <span
            key={`${link.entity_type}-${link.label}`}
            className={cn(
              tagClass,
              'max-w-[15rem] bg-white text-foreground ring-1 ring-border ring-inset',
              isId && 'font-mono text-[11.5px]',
            )}
            title={`${link.entity_type.replace('_', ' ')}: ${link.label}`}
          >
            <Icon className="size-3 shrink-0 text-primary" aria-hidden="true" />
            <span className="truncate">{link.label}</span>
          </span>
        )
      })}
      {hidden.length > 0 && (
        <span
          className="text-xs text-muted-foreground"
          title={hidden.map((l) => l.label).join(', ')}
        >
          +{hidden.length}
        </span>
      )}
    </span>
  )
}
