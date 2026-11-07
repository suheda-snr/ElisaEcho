import {
  CircleCheck,
  CirclePlay,
  CircleHelp,
  Lightbulb,
  ScanSearch,
  Siren,
  type LucideIcon,
} from 'lucide-react'

import type { GuideNodeType, SupportLevel } from '@/types/api'

export const nodeTypeStyle: Record<
  GuideNodeType,
  { label: string; icon: LucideIcon; accent: string; chip: string }
> = {
  start: {
    label: 'Start',
    icon: CirclePlay,
    accent: 'border-l-slate-500',
    chip: 'bg-slate-100 text-slate-700',
  },
  question: {
    label: 'Question',
    icon: CircleHelp,
    accent: 'border-l-blue-600',
    chip: 'bg-blue-50 text-blue-800',
  },
  diagnostic: {
    label: 'Diagnostic',
    icon: ScanSearch,
    accent: 'border-l-indigo-500',
    chip: 'bg-indigo-50 text-indigo-800',
  },
  recommendation: {
    label: 'Recommendation',
    icon: Lightbulb,
    accent: 'border-l-amber-500',
    chip: 'bg-amber-50 text-amber-900',
  },
  resolution: {
    label: 'Resolution',
    icon: CircleCheck,
    accent: 'border-l-emerald-600',
    chip: 'bg-emerald-50 text-emerald-800',
  },
  escalation: {
    label: 'Escalation',
    icon: Siren,
    accent: 'border-l-red-600',
    chip: 'bg-red-50 text-red-800',
  },
}

export const supportStyle: Record<SupportLevel, { label: string; className: string } | null> = {
  approved: {
    label: 'Expert-approved',
    className: 'bg-emerald-50 text-emerald-800',
  },
  confirmed_in_conversation: {
    label: 'Worked in chat · not approved',
    className: 'bg-blue-50 text-blue-800',
  },
  suggested: {
    label: 'Suggested · unverified',
    className: 'bg-slate-50 text-slate-700',
  },
  conflicting: {
    label: 'Conflicting evidence',
    className: 'bg-amber-50 text-amber-900',
  },
  none: null,
}
